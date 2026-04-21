import cv2
import pytesseract
from pytesseract import Output
import numpy as np
from pathlib import Path
from src.logger import get_logger

logger = get_logger(__name__)

class OCREngine:
    def __init__(self):
        self.custom_config = r'--oem 3 --psm 6'

    def _remove_green_noise(self, img: np.ndarray) -> np.ndarray:
        """
        Detecta píxeles verdes y azules (líneas de conexión, íconos en Intermapper)
        y los convierte en blanco puro para que no interfieran con el texto.
        """
        # 1. Convertir la imagen de BGR (formato por defecto de OpenCV) a HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 2. Definir el rango del color verde y azulen HSV
        # En OpenCV, Hue (Tono) va de 0 a 179. El verde está entre 35 y 85.
        # Saturation y Value van de 0 a 255. Ponemos un rango amplio para captar tonos oscuros y claros.
        lower_green = np.array([15, 30, 30])
        upper_green = np.array([85, 255, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)

        # Rango Azul (Cubre desde cian oscuro hasta azul marino)
        lower_blue = np.array([90, 50, 50])
        upper_blue = np.array([150, 255, 255])
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

        # 3. Combinar máscaras (Verde O Azul)
        mask_combined = cv2.bitwise_or(mask_green, mask_blue)

        # 4. Reemplazar los píxeles detectados por la máscara con color blanco (255, 255, 255 en BGR)
        img_cleaned = img.copy()
        img_cleaned[mask_combined > 0] = (255, 255, 255)

        return img_cleaned

    def extract_text(self, image_path: Path) -> dict:
        logger.info(f"Procesando imagen con Filtrado de Color y ROI: {image_path.name}")
        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"No se pudo cargar: {image_path}")

        # DEFENSA CROMÁTICA ANTES DE CUALQUIER PROCESAMIENTO ---
        img = self._remove_green_noise(img)
        
        # (Opcional) Guarda la imagen limpia general para ver la magia
        #cv2.imwrite(f"debug_sin_verde_{image_path.name}", img)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        gray_base = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # --- PASADA 1: BÚSQUEDA ESPACIAL ---  
        logger.info("Detectando coordenadas de dispositivos OSNAP...")
        d = pytesseract.image_to_data(gray_base, output_type=Output.DICT, config=r'--oem 3 --psm 11')
        
        n_boxes = len(d['text'])
        header_text = ""
        extracted_blocks = []
        header_found = False

        for i in range(n_boxes):
            word = d['text'][i]
            word_upper = word.upper()

            # ---DETECCIÓN Y ZOOM DEL ENCABEZADO (Coordenadas) ---
            if not header_found and ('MAP:' in word_upper or 'OSN' in word_upper):
                x, y, w, h = d['left'][i], d['top'][i], d['width'][i], d['height'][i]
                
                # Definimos una zona amplia alrededor del título (600px de ancho, 300px abajo)
                h_x_start = max(0, x - 50)
                h_y_start = max(0, y - 50)
                h_x_end = min(gray_base.shape[1], x + 1000)
                h_y_end = min(gray_base.shape[0], y + 300)
                
                header_roi = gray_base[h_y_start:h_y_end, h_x_start:h_x_end]
                
                # Aplicamos el mismo tratamiento que a los APs: Zoom + Limpieza
                header_zoomed = cv2.resize(header_roi, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
                _, header_bin = cv2.threshold(cv2.medianBlur(header_zoomed, 3), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Opcional: Debug para ver si el recorte del encabezado es correcto
                # cv2.imwrite(f"debug_header_{image_path.name}", header_bin)
                
                header_text = pytesseract.image_to_string(header_bin, config='--oem 3 --psm 3')
                header_found = True
                logger.info(f"[{image_path.name}] Encabezado procesado con alta resolución.")

            if 'OSNAP' in word.upper():
                x, y, w, h = d['left'][i], d['top'][i], d['width'][i], d['height'][i]

                # --- PASADA 2: RECORTAR (CROP) LA REGIÓN ---
                margen_izq = 30
                margen_der = 250   
                margen_arriba = 20
                margen_abajo = 250 

                y_start = max(0, y - margen_arriba)
                y_end = min(gray_base.shape[0], y + h + margen_abajo)
                x_start = max(0, x - margen_izq)
                x_end = min(gray_base.shape[1], x + w + margen_der)

                roi = gray_base[y_start:y_end, x_start:x_end]

                # --- EL SÚPER ZOOM Y LIMPIEZA ---
                roi_zoomed = cv2.resize(roi, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
                blur = cv2.medianBlur(roi_zoomed, 3)
                
                # Binarización Otsu
                _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                # Operación Morfológica
                kernel = np.ones((2, 2), np.uint8)
                binary = cv2.dilate(binary, kernel, iterations=1)
                binary = cv2.erode(binary, kernel, iterations=1)

                clean_name = word.replace(':', '').replace('|', '').replace('/', '')
                #cv2.imwrite(f"debug_roi_{clean_name}_{i}.png", binary)

                block_text = pytesseract.image_to_string(binary, config=self.custom_config)
                extracted_blocks.append(block_text)

        return {
            "header_text": header_text,
            "devices_text": "\n--- NUEVO BLOQUE AP ---\n".join(extracted_blocks),
        }