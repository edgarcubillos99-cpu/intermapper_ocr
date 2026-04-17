import re
from src.logger import get_logger

logger = get_logger(__name__)

class DataExtractor:
    @staticmethod
    def _clean_ap_name(val: str) -> str:
        # Corrige el error común de OCR donde lee "L0" o "LO" en vez de "10"
        return val.replace('LO', '10').replace('L0', '10')

    @staticmethod
    def extract_ap_data(raw_text: str, tower_name: str) -> list:
        # 1. Separar el texto crudo usando el delimitador que inyectamos en el OCR
        blocks = raw_text.split('--- NUEVO BLOQUE AP ---')
        devices = []
        
        logger.info(f"Procesando {len(blocks) - 1} bloques detectados para la torre {tower_name}")

        for block in blocks:
            block = block.strip()
            
            # Descartar bloques vacíos o basura que no contengan un OSNAP
            if not block or 'OSNAP' not in block.upper():
                continue
                
            # --- 1. Nombre del AP ---
            ap_match = re.search(r'(OSNAP[A-Za-z0-9\-]+)', block, re.IGNORECASE)
            ap_name = DataExtractor._clean_ap_name(ap_match.group(1).upper()) if ap_match else "DESCONOCIDO"
            
            # --- 2. Tipo de AP ---
            ap_type = "DESCONOCIDO"
            block_upper = block.upper()
            if 'AC' in block_upper: ap_type = "Rocket AC"
            elif 'EPMP' in block_upper or 'FORCE' in block_upper: ap_type = "ePMP"
            elif 'C5C' in block_upper: ap_type = "Mimosa C5c"
            
            # --- 3. Azimut (Regla defensiva) ---
            # Busca de 1 a 3 dígitos, ignora basura, busca la orientación
            az_match = re.search(r'(\d{1,3})[^NSEOW\d]*?([NSEOW]{1,2})\b', block, re.IGNORECASE)
            azimut = f"{az_match.group(1)}Â°{az_match.group(2).upper()}" if az_match else "N/A"
            
            # --- 4. Altura (Regla defensiva) ---
            # Atrapa los dígitos, ignora basura (', ’, 7, °), y requiere f/t
            alt_match = re.search(r'(\d{1,3})\s*[\'’´7°]?\s*[fF][tT]', block)
            altura = f"{alt_match.group(1)} Ft" if alt_match else "N/A"

            # --- 5. Tilt (Ajuste para til, till, tilt) ---
            tilt = "N/A"
            # til[l]?[t]? permite atrapar "til", "till", y "tilt"
            tilt_match = re.search(r'(til[l]?[t]?\s*[-]?\d+|ofeso\s*\d*|eor\'?o\s*\d*|eso\s*\d*|feso\s*\d*)', block, re.IGNORECASE)
            
            if tilt_match:
                raw_tilt = tilt_match.group(1).lower().replace(' ', '')
                if any(bad in raw_tilt for bad in ['ofeso', 'eor', 'eso', 'feso']):
                    tilt = 'tilt0'
                else:
                    # Normalizamos la palabra base (reemplaza til o till por tilt)
                    raw_tilt = re.sub(r'^til[l]?[t]?', 'tilt', raw_tilt)
                    # Corregimos si Tesseract confundió el signo menos con un 7
                    tilt = raw_tilt.replace('tilt7', 'tilt-')

            # Ensamblaje del diccionario
            devices.append({
                "Torre": tower_name,
                "AP_Name": ap_name,
                "Tipo": ap_type,
                "Azimut": azimut,
                "Tilt": tilt,
                "Altura": altura
            })
                
        return devices