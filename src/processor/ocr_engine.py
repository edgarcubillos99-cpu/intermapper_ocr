import cv2
import pytesseract
import numpy as np
from pathlib import Path
from src.logger import get_logger

logger = get_logger(__name__)

class OCREngine:
    def __init__(self):
        # Configuramos Tesseract para que asuma un bloque de texto uniforme (--psm 6) o disperso (--psm 11)
        # El psm 11 (Sparse text) suele funcionar mejor para mapas de red
        self.custom_config = r'--oem 3 --psm 11'

    def preprocess_image(self, image_path: Path) -> np.ndarray:
        """
        Limpia la imagen usando OpenCV para mejorar la precisión de Tesseract.
        """
        logger.info(f"Preprocesando imagen: {image_path.name}")
        
        # 1. Cargar imagen
        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"No se pudo cargar la imagen: {image_path}")

        # 2. Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 3. Escalar la imagen (hacerla más grande ayuda a Tesseract con textos pequeños)
        # Ampliamos al 200% usando interpolación cúbica
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

        # 4. Aplicar un filtro bilateral para quitar ruido pero mantener los bordes del texto afilados
        blur = cv2.bilateralFilter(gray, 9, 75, 75)

        # 5. Binarización adaptativa (convierte a blanco y negro puro, ideal para fondos irregulares)
        # El texto quedará negro sobre fondo blanco
        binary = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
        )

        return binary

    def extract_text(self, image_path: Path) -> str:
        """
        Preprocesa la imagen y extrae todo el texto crudo.
        """
        try:
            processed_img = self.preprocess_image(image_path)
            
            # (pruebas) guardar la imagen procesada para ver cómo la está viendo Tesseract
            cv2.imwrite(f"debug_{image_path.name}", processed_img)

            logger.info("Extrayendo texto con Tesseract...")
            text = pytesseract.image_to_string(processed_img, config=self.custom_config)
            
            return text
        except Exception as e:
            logger.error(f"Error procesando {image_path.name}: {e}")
            return ""