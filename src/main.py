import os
import time
import asyncio
from pathlib import Path
import concurrent.futures

# CONTROLAR A TESSERACT ---
# Evita que cada worker de PyTesseract sature la CPU intentando usar multithreading interno
os.environ['OMP_THREAD_LIMIT'] = '1'
#os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata' # O la ruta de tu tessdata

from src.logger import get_logger
from src.processor.ocr_engine import OCREngine
from src.processor.extractor import DataExtractor
from src.database.db_manager import DBManager
from src.scraper.browser import BrowserManager
from src.scraper.device_ip_flow import run_device_ip_phase
from src.scraper.navigator import IntermapperScraper
from src.scraper.tower_naming import tower_name_from_screenshot_stem
from src.config import Config

logger = get_logger(__name__)

def process_single_tower(tower_name: str, image_path: Path):
    """WORKER FUNCTION: Corre en su propio proceso"""
    logger.info(f"[{tower_name}] Iniciando procesamiento en PID: {os.getpid()}")
    try:
        ocr = OCREngine()
        db = DBManager()
        
        ocr_result = ocr.extract_text(image_path)
        devices = DataExtractor.extract_ap_data(ocr_result["devices_text"], tower_name)
        coords = DataExtractor.extract_coordinates(ocr_result.get("header_text") or "")

        if devices:
            db.save_site_data(tower_name, str(image_path), devices, coords)
            logger.info(f"[{tower_name}] ✅ {len(devices)} dispositivos guardados/actualizados.")
        else:
            logger.warning(f"[{tower_name}] ⚠️ No se detectaron dispositivos OSNAP.")
            
        return {"status": "success", "torre": tower_name, "count": len(devices)}
    except Exception as e:
        logger.error(f"[{tower_name}] ❌ Error crítico: {e}")
        return {"status": "error", "torre": tower_name, "error": str(e)}

async def run_scraper_phase():
    """Ejecuta la Fase 1: Navegación Asíncrona con Playwright"""
    logger.info("--- INICIANDO FASE 1: NAVEGACIÓN Y CAPTURAS ---")
    browser_manager = BrowserManager()
    context = await browser_manager.start()
    
    scraper = IntermapperScraper(context)
    page = await scraper.login()
    
    urls = await scraper.get_site_links(page)
    await page.close()

    semaphore = asyncio.Semaphore(Config.WORKERS)
    
    # Navegamos y capturamos cada submapa de manera controlada
    tasks = [scraper.process_site(url, semaphore) for url in urls]
    results = await asyncio.gather(*tasks)

    await browser_manager.stop()

    sites_to_process = [r for r in results if r is not None]
    if not sites_to_process:
        for screenshot_path in Config.SCREENSHOT_DIR.glob("*.png"):
            tower_name = tower_name_from_screenshot_stem(screenshot_path.stem)
            sites_to_process.append((tower_name, screenshot_path, None))

    return sites_to_process

def main():
    logger.info("Iniciando Pipeline de Extracción Intermapper de Alto Rendimiento...")
    start_time = time.time()
    Config.setup_directories()
    
    # FASE 1: SCRAPING (I/O Bound) - Ejecutado en el Loop de Eventos
    sites_to_process = asyncio.run(run_scraper_phase())

    logger.info(f"Fase 1 completada. {len(sites_to_process)} capturas listas para OCR.")

    # FASE 2: PROCESAMIENTO PARALELO OCR (CPU Bound)
    if not sites_to_process:
        logger.warning("No se generaron capturas. Finalizando.")
        return

    logger.info("--- INICIANDO FASE 2: PROCESAMIENTO MULTI-CORE ---")
    max_cores = max(1, os.cpu_count() - 2)

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_cores) as executor:
        futures = {
            executor.submit(process_single_tower, tower, path): tower
            for tower, path, _url in sites_to_process
        }
        
        for future in concurrent.futures.as_completed(futures):
            torre = futures[future]
            try:
                future.result()
            except Exception as exc:
                logger.error(f"💥 El worker de {torre} generó una excepción: {exc}")

    by_tower_url: dict[str, str] = {}
    for t, _p, u in sites_to_process:
        if u:
            by_tower_url[t] = u
    site_urls_for_ips = list(by_tower_url.items())
    if site_urls_for_ips:
        asyncio.run(run_device_ip_phase(site_urls_for_ips))
    else:
        logger.info("Fase 3 omitida: no hay URL de submapa por torre (¿solo capturas locales?).")

    logger.info("=" * 60)
    logger.info(f"🚀 PIPELINE COMPLETADO EN {time.time() - start_time:.2f} SEGUNDOS 🚀")
    logger.info("=" * 60)

if __name__ == '__main__':
    # Necesario para multiprocessing en Windows/macOS
    import multiprocessing
    multiprocessing.freeze_support()
    main()