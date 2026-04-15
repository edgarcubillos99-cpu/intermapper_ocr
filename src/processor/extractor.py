import re
from src.logger import get_logger

logger = get_logger(__name__)

class DataExtractor:
    @staticmethod
    def _clean_ap_name(val: str) -> str:
        return val.replace('LO', '10').replace('L0', '10')

    @staticmethod
    def _clean_azimut(val: str) -> str:
        val = val.upper()
        if val.startswith('S'): val = '5' + val[1:]
        if val.startswith('O'): val = '0' + val[1:]
        val = val.replace('P', '°').replace('A°', 'Aº')
        return val

    @staticmethod
    def _clean_tilt(val: str) -> str:
        val = val.lower().replace(' ', '')
        if any(bad_word in val for bad_word in ['ofeso', 'eor', 'eso', 'feso']):
            return 'tilt0'
        val = val.replace('tilt7', 'tilt-')
        return val

    @staticmethod
    def _clean_altura(val: str) -> str:
        """
        Implementa la regla: Si hay un caracter basura justo antes de 'ft', bórralo.
        Ej: 67ft -> 6 ft | 127ft -> 12 ft | 6'fft -> 6 ft
        """
        val = val.lower().replace(' ', '')
        
        # Regex captura los dígitos iniciales. 
        # ".+?" obliga a capturar (y descartar) al menos 1 caracter de basura antes de "ft"
        match = re.search(r'^(\d+).+?f*t', val)
        if match:
            return f"{match.group(1)} ft"
            
        # Fallback por si la imagen es tan nítida que Tesseract leyó exactamente "6ft"
        match_clean = re.search(r'^(\d+)f*t', val)
        if match_clean:
             return f"{match_clean.group(1)} ft"
             
        return val

    @staticmethod
    def extract_ap_data(raw_text: str, tower_name: str) -> list:
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        devices = []
        
        for i, line in enumerate(lines):
            if 'OSNAP' in line.upper():
                
                ap_match = re.search(r'(OSNAP[A-Za-z0-9\-]+)', line, re.IGNORECASE)
                ap_name = "DESCONOCIDO"
                if ap_match:
                    ap_name = DataExtractor._clean_ap_name(ap_match.group(1).upper())
                
                ap_type = "DESCONOCIDO"
                if 'AC' in line.upper(): ap_type = "Rocket AC"
                elif 'EPMP' in line.upper() or 'FORCE' in line.upper(): ap_type = "ePMP"
                elif 'C5C' in line.upper(): ap_type = "Mimosa C5c"
                
                azimut, tilt, altura = "N/A", "N/A", "N/A"
                
                for j in range(1, min(7, len(lines) - i)):
                    lookahead = lines[i+j]
                    if 'OSNAP' in lookahead.upper(): break
                    
                    if azimut == "N/A":
                        az_match = re.search(r'([A-Za-z0-9]{2,3}[°º^P]+[NSEWO]{1,2})', lookahead, re.IGNORECASE)
                        if az_match:
                            azimut = DataExtractor._clean_azimut(az_match.group(1))
                    
                    if tilt == "N/A":
                        tilt_match = re.search(r'(tilt\s*[-]?\d+|ofeso|eor\'?o|eso|feso)', lookahead, re.IGNORECASE)
                        if tilt_match:
                            tilt = DataExtractor._clean_tilt(tilt_match.group(1))
                            
                    if altura == "N/A":
                        # Atrapa cualquier cadena que empiece con números y termine cerca de ft
                        altura_match = re.search(r'(\d+.*?f*t)', lookahead, re.IGNORECASE)
                        if altura_match:
                            altura = DataExtractor._clean_altura(altura_match.group(1))

                devices.append({
                    "Torre": tower_name,
                    "AP_Name": ap_name,
                    "Tipo": ap_type,
                    "Azimut": azimut,
                    "Tilt": tilt,
                    "Altura": altura
                })
                
        return devices