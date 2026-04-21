import re
from src.logger import get_logger

logger = get_logger(__name__)

class DataExtractor:
    @staticmethod
    def _clean_ap_name(val: str) -> str:
        # Corrige el error común de OCR donde lee "L0" o "LO" en vez de "10"
        return val.replace('LO', '10').replace('L0', '10')

    @staticmethod
    def extract_coordinates(text: str):
        """
        Extrae coordenadas usando un 'Cerco Geográfico Estricto' (Bounding Box PR).
        Evita colisiones cuando los decimales de la latitud empiezan por 6 (Ej: 18,619...).
        """
        if not text:
            return None, None
            
        search_block = text
        context_match = re.search(r'(Map:|OSN[.,_\- ]*)', text, re.IGNORECASE)
        
        if context_match:
            start_idx = context_match.start()
            search_block = text[start_idx:start_idx+250] 

        # --- PASO 2: CERCO GEOGRÁFICO ESTRICTO ---
        # LATITUD: Empieza con 1, sigue con 7, 8 o 9 (o S para 8). Ej: 18
        # LONGITUD: Empieza con 6 (o G), sigue con 5, 6 o 7 (o S para 5/6). Ej: -66
        # [.,\s]* permite cualquier cantidad de comas, puntos o espacios en el medio
        coord_pattern = r"([-~_]?\s*[1Il]\s*[789Ss][.,\s]*[\dOoIilSs\s]{3,20})[^\d-]{1,30}([-~_]?\s*[6G]\s*[567Ss][.,\s]*[\dOoIilSs\s]{3,20})"
        
        match = re.search(coord_pattern, search_block, re.IGNORECASE)
        
        if match:
            # --- PASO 3: LA APLANADORA ABSOLUTA ---
            def clean_coordinate(raw_str):
                s = re.sub(r'\s+', '', raw_str).lower()
                s = s.replace('s', '8').replace('o', '0').replace('l', '1').replace('i', '1').replace('g', '6')
                
                # Reemplazar cualquier bloque de puntos/comas por un solo punto
                s = re.sub(r'[.,]+', '.', s)
                s = s.replace('~', '-').replace('_', '-')
                
                # Forzar un ÚNICO punto decimal (Si Tesseract leyó "18.61.930")
                if '.' in s:
                    parts = s.split('.')
                    s = parts[0] + '.' + ''.join(parts[1:])
                    
                return s

            lat = clean_coordinate(match.group(1))
            lon = clean_coordinate(match.group(2))
            
            # --- PASO 4: INYECTOR DE PUNTO (Si desapareció) ---
            def inject_missing_dot(coord_str):
                if '.' in coord_str:
                    return coord_str
                
                offset = 1 if coord_str.startswith('-') else 0
                insert_pos = offset + 2 
                
                if len(coord_str) > insert_pos:
                    return coord_str[:insert_pos] + '.' + coord_str[insert_pos:]
                return coord_str

            lat = inject_missing_dot(lat)
            lon = inject_missing_dot(lon)
            
            return lat, lon
            
        return None, None

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