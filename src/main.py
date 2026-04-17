import os
import time
from pathlib import Path
import concurrent.futures
from src.logger import get_logger
from src.processor.ocr_engine import OCREngine
from src.processor.extractor import DataExtractor
from src.database.db_manager import DBManager

# Asumo que tienes tu navegador importado (descomenta según tus archivos reales)
# from src.scraper.navigator import Navigator

logger = get_logger(__name__)

def process_single_tower(tower_name: str, image_path: Path):
    """
    WORKER FUNCTION: Esta función se ejecuta en un núcleo de CPU independiente.
    Es vital instanciar las clases pesadas (OCR y DB) DENTRO de esta función 
    para evitar choques de memoria entre procesos (Pickling Errors).
    """
    logger.info(f"[{tower_name}] Iniciando procesamiento en PID: {os.getpid()}")
    
    try:
        # 1. Instancias locales exclusivas para este proceso
        ocr = OCREngine()
        db = DBManager()
        
        # 2. Extraer texto crudo (Operación pesada de CPU)
        logger.info(f"[{tower_name}] Ejecutando OpenCV y Tesseract...")
        raw_text = ocr.extract_text(image_path)
        
        # 3. Extraer datos estructurados con Regex
        devices = DataExtractor.extract_ap_data(raw_text, tower_name)
        
        # 4. Guardar en Base de Datos MySQL
        if devices:
            db.save_site_data(tower_name, str(image_path), devices)
            logger.info(f"[{tower_name}] ✅ {len(devices)} dispositivos guardados en BD.")
        else:
            logger.warning(f"[{tower_name}] ⚠️ No se detectaron dispositivos OSNAP.")
            
        return {"status": "success", "torre": tower_name, "count": len(devices)}
    
    except Exception as e:
        logger.error(f"[{tower_name}] ❌ Error crítico: {e}")
        return {"status": "error", "torre": tower_name, "error": str(e)}


def main():
    logger.info("Iniciando Pipeline de Extracción Intermapper de Alto Rendimiento...")
    start_time = time.time()
    
    # =========================================================
    # FASE 1: SCRAPING (I/O Bound)
    # =========================================================
    logger.info("--- INICIANDO FASE 1: NAVEGACIÓN Y CAPTURAS ---")
    
    # Aquí irá el loop de tu scraper. El objetivo es que devuelva una 
    # lista de tuplas con el nombre de la torre y la ruta de la imagen generada.
    
    nav = Navigator()
    nav.login()
    sites_to_process = nav.capture_all_towers() # Implementación sugerida
    
    logger.info(f"Fase 1 completada. {len(sites_to_process)} capturas en cola.")
    
    # =========================================================
    # FASE 2: PROCESAMIENTO PARALELO OCR (CPU Bound)
    # =========================================================
    logger.info("--- INICIANDO FASE 2: PROCESAMIENTO MULTI-CORE ---")
    
    # Dejamos 1 o 2 núcleos libres para el Sistema Operativo y MySQL
    max_cores = max(1, os.cpu_count() - 2) 
    logger.info(f"Encendiendo motores de OCR... Utilizando {max_cores} núcleos.")
    
    # IMPORTANTE: Usamos ProcessPoolExecutor en lugar de ThreadPoolExecutor.
    # Los hilos (Threads) en Python comparten memoria (GIL) y no sirven para tareas
    # matemáticas pesadas como OpenCV. Los Procesos sí usan CPUs reales.
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_cores) as executor:
        
        # Mapeamos las tareas a los procesadores libres
        futures = {
            executor.submit(process_single_tower, tower, path): tower 
            for tower, path in sites_to_process
        }
        
        # A medida que cada núcleo termina su imagen, capturamos el resultado
        for future in concurrent.futures.as_completed(futures):
            torre = futures[future]
            try:
                result = future.result()
                if result['status'] == 'success':
                    logger.info(f"🏆 Finalizado: {torre}")
            except Exception as exc:
                logger.error(f"💥 El worker de {torre} generó una excepción: {exc}")

    # =========================================================
    # CIERRE Y MÉTRICAS
    # =========================================================
    elapsed_time = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"🚀 PIPELINE COMPLETADO EN {elapsed_time:.2f} SEGUNDOS 🚀")
    logger.info("=" * 60)

if __name__ == '__main__':
    main()