# test_ocr.py
import json
import re
from pathlib import Path
from src.processor.ocr_engine import OCREngine
from src.processor.extractor import DataExtractor
from src.config import Config

def clean_tower_name(filename: str) -> str:
    """Extrae el nombre limpio de la torre desde el archivo."""
    name = re.sub(r'^(Map_and_Charts__|Map__)', '', filename, flags=re.IGNORECASE)
    return name.replace('_', ' ').strip()

def test_full_extraction():
    screenshots = list(Config.SCREENSHOT_DIR.glob("*.png"))
    if not screenshots:
        print("No hay capturas para probar.")
        return

    # Usaremos Cercadillo u otra que tengas ahí
    test_image = screenshots[0] 
    tower_name = clean_tower_name(test_image.stem)
    
    print(f"📡 PROCESANDO TORRE: {tower_name}")
    print("=" * 60)

    # 1. Extraer texto crudo (Fase 2)
    engine = OCREngine()
    ocr_result = engine.extract_text(test_image)

    # 2. Procesar datos estructurados (Fase 3)
    structured_data = DataExtractor.extract_ap_data(ocr_result["devices_text"], tower_name)

    # 3. Mostrar en JSON bonito
    print(json.dumps(structured_data, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    test_full_extraction()