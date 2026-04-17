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
        Detecta píxeles verdes (líneas de conexión, íconos de estado en Intermapper)
        y los convierte en blanco puro para que no interfieran con el texto.
        """
        # 1. Convertir la imagen de BGR (formato por defecto de OpenCV) a HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 2. Definir el rango del color verde en HSV
        # Nota: En OpenCV, Hue (Tono) va de 0 a 179. El verde está entre 35 y 85.
        # Saturation y Value van de 0 a 255. Ponemos un rango amplio para captar tonos oscuros y claros.
        lower_green = np.array([15, 30, 30])
        upper_green = np.array([85, 255, 255])

        # 3. Crear una máscara (una imagen en blanco y negro donde lo blanco es lo verde)
        mask = cv2.inRange(hsv, lower_green, upper_green)

        # 4. Reemplazar los píxeles detectados por la máscara con color blanco (255, 255, 255 en BGR)
        img_cleaned = img.copy()
        img_cleaned[mask > 0] = (255, 255, 255)

        return img_cleaned

    def extract_text(self, image_path: Path) -> str:
        logger.info(f"Procesando imagen con Filtrado de Color y ROI: {image_path.name}")
        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"No se pudo cargar: {image_path}")

        # --- NUEVO: DEFENSA CROMÁTICA ANTES DE CUALQUIER PROCESAMIENTO ---
        img = self._remove_green_noise(img)
        
        # (Opcional) Guarda la imagen limpia general para que veas la magia
        cv2.imwrite(f"debug_sin_verde_{image_path.name}", img)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # --- PASADA 1: BÚSQUEDA ESPACIAL ---
        gray_base = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        logger.info("Detectando coordenadas de dispositivos OSNAP...")
        d = pytesseract.image_to_data(gray_base, output_type=Output.DICT, config=r'--oem 3 --psm 11')

        n_boxes = len(d['text'])
        extracted_blocks = []

        for i in range(n_boxes):
            word = d['text'][i]
            
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
                roi_zoomed = cv2.resize(roi, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                blur = cv2.bilateralFilter(roi_zoomed, 9, 75, 75)
                
                # Binarización Otsu
                _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                # Operación Morfológica
                kernel = np.ones((2, 2), np.uint8)
                binary = cv2.dilate(binary, kernel, iterations=1)
                binary = cv2.erode(binary, kernel, iterations=1)

                clean_name = word.replace(':', '').replace('|', '').replace('/', '')
                cv2.imwrite(f"debug_roi_{clean_name}_{i}.png", binary)

                block_text = pytesseract.image_to_string(binary, config=self.custom_config)
                extracted_blocks.append(block_text)

        final_text = "\n--- NUEVO BLOQUE AP ---\n".join(extracted_blocks)
        return final_text