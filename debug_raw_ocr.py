import sys
from pathlib import Path
from src.processor.ocr_engine import OCREngine

def main():
    # Por defecto buscará 'imagen.png' o el nombre que le pases por consola
    image_name = sys.argv[1] if len(sys.argv) > 1 else 'imagen.png'
    image_path = Path(image_name)

    if not image_path.exists():
        print(f"❌ Error: No se encontró la imagen '{image_name}' en la ruta actual.")
        print("Uso: python debug_raw_ocr.py [nombre_imagen.png]")
        return

    print("="*60)
    print(f"🔍 MODO DEBUG: LEYENDO TEXTO CRUDO DE '{image_name}'")
    print("="*60)

    # Inicializamos el motor OCR (con las mejoras morfológicas que hicimos en la Fase 2)
    engine = OCREngine()
    
    print("Procesando imagen con OpenCV y Tesseract...\n")
    # Extraemos el texto
    raw_text = engine.extract_text(image_path)
    
    print("📝 --- INICIO DEL TEXTO CRUDO EXTRAÍDO --- 📝\n")
    print(raw_text)
    print("\n📝 --- FIN DEL TEXTO CRUDO EXTRAÍDO --- 📝")
    print("="*60)
    
    # Recordatorio útil
    debug_img_path = f"debug_{image_path.name}"
    print(f"\n💡 CONSEJO: Abre el archivo '{debug_img_path}' que se acaba de generar.")
    print("Ahí podrás ver cómo ve Tesseract la imagen después del filtro blanco y negro.")

if __name__ == "__main__":
    main()