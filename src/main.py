import asyncio
from src.config import Config
from src.logger import get_logger
from src.scraper.browser import BrowserManager
from src.scraper.navigator import IntermapperScraper

logger = get_logger("main")

async def main():
    logger.info("🚀 Iniciando automatización de Intermapper (Fase 1)")
    Config.setup_directories()
    
    browser_manager = BrowserManager()
    context = await browser_manager.start()
    
    try:
        scraper = IntermapperScraper(context)
        
        # 1. Login y obtener la página principal
        main_page = await scraper.login()
        
        # 2. Extraer todos los links de los submapas
        # Para pruebas, puedes comentar esto y usar una lista estática de 2 URLs
        site_links = await scraper.get_site_links(main_page)
        
        # Limitar para pruebas (ej. procesar solo los primeros 5)
        site_links = site_links[:5] 
        
        # 3. Procesar en paralelo usando asyncio.gather y un Semáforo
        # El semáforo evita que abramos 500 pestañas de golpe y saturemos la RAM
        semaphore = asyncio.Semaphore(Config.WORKERS)
        
        tasks = [scraper.process_site(link, semaphore) for link in site_links]
        
        logger.info(f"Iniciando procesamiento concurrente con {Config.WORKERS} workers...")
        await asyncio.gather(*tasks)
        
        logger.info("✅ Fase 1 completada exitosamente.")
        
    except Exception as e:
        logger.error(f"Fallo crítico en la ejecución: {e}")
    finally:
        await browser_manager.stop()

if __name__ == "__main__":
    asyncio.run(main())