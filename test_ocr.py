import sys
from pathlib import Path
from src.processor.ocr_engine import OCREngine

def test_raw_extraction(image_path: str):
    path = Path(image_path)
    if not path.exists():
        print(f"❌ Error: No se encontró la imagen en {path}")
        return

    print(f"🔍 Procesando imagen cruda: {path.name}...")
    print("Iniciando motor OCR... (esto puede tardar unos segundos)\n")
    
    try:
        ocr = OCREngine()
        # Extraemos el texto en crudo usando tu motor
        resultados = ocr.extract_text(path)
        
        print("="*60)
        print("📍 TEXTO DEL ENCABEZADO (Buscando Lat/Lon)")
        print("="*60)
        # Reemplazamos espacios en blanco múltiples para ver exactamente qué hay
        header = resultados.get('header_text', '')
        print(repr(header)) # repr() muestra los saltos de línea como \n y nos ayuda a ver caracteres ocultos
        print("\n" + header)
        print("\n")
        
        print("="*60)
        print("📡 TEXTO DE LOS DISPOSITIVOS (Bloques de APs)")
        print("="*60)
        devices = resultados.get('devices_text', '')
        print(devices)
        print("\n")
        
        print("="*60)
        print("✅ Prueba finalizada.")
        print("Copia y pega la salida del texto del encabezado y de un AP que esté fallando para ajustar el Regex.")
        
    except Exception as e:
        print(f"❌ Ocurrió un error crítico durante el OCR: {e}")

if __name__ == '__main__':
    # Permite pasar la ruta de la imagen por consola
    if len(sys.argv) < 2:
        print("Uso correcto: python test_ocr.py <ruta_a_la_imagen.png>")
        print("Ejemplo: python test_ocr.py Map_and_Charts__Filtros.png")
    else:
        test_raw_extraction(sys.argv[1])