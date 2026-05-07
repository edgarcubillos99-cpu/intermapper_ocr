import sys
import json
from pathlib import Path
from src.processor.ocr_engine import OCREngine
from src.processor.extractor import DataExtractor # <-- Importamos tu extractor actualizado

def test_full_pipeline(image_path: str):
    path = Path(image_path)
    if not path.exists():
        print(f"❌ Error: No se encontró la imagen en {path}")
        return

    print(f"🔍 Procesando imagen: {path.name}...")
    print("Iniciando motor OCR y Extractor... (esto puede tardar unos segundos)\n")
    
    try:
        # 1. Capa de Extracción Cruda (OpenCV + Tesseract)
        ocr = OCREngine()
        resultados_crudos = ocr.extract_text(path)
        
        # 2. Obtenemos los textos
        header_raw = resultados_crudos.get('header_text', '')
        devices_raw = resultados_crudos.get('devices_text', '')

        print("="*60)
        print("📡 TEXTO CRUDO DE TESSERACT (Capa 1 - OCREngine)")
        print("="*60)
        print(devices_raw)
        print("\n")

        print("="*60)
        print("🛠️ DATOS FINALES ESTRUCTURADOS (Capa 2 - DataExtractor)")
        print("="*60)
        
        # 3. Capa de Limpieza (Regex + Traducción de Errores)
        lat, lon = DataExtractor.extract_coordinates(header_raw)
        print(f"📍 Coordenadas Extraídas: Lat: {lat}, Lon: {lon}\n")

        # Aquí es donde ocurre la magia de la corrección del Azimut
        dispositivos_limpios = DataExtractor.extract_ap_data(devices_raw, tower_name="Torre_Prueba")
        
        # Imprimimos en formato JSON para que sea fácil de leer
        print(json.dumps(dispositivos_limpios, indent=4, ensure_ascii=False))
        
        print("\n" + "="*60)
        print("✅ Prueba finalizada.")
        print("Revisa la salida estructurada de arriba. El Azimut 'F2' ahora debería ser '72°E'.")
        
    except Exception as e:
        print(f"❌ Ocurrió un error crítico durante la prueba: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso correcto: python test_ocr.py <ruta_a_la_imagen.png>")
        print("Ejemplo: python test_ocr.py Map_and_Charts__Filtros.png")
    else:
        test_full_pipeline(sys.argv[1])