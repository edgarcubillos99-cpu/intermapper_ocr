import time
import schedule
import multiprocessing
from src.logger import get_logger
from src.main import main

logger = get_logger(__name__)

def job():
    """Función envoltura que ejecuta tu pipeline principal"""
    logger.info("🕒 Iniciando ejecución programada semanal...")
    try:
        # Llama a la función main() de main.py
        main()
        logger.info("✅ Ejecución programada finalizada con éxito.")
    except Exception as e:
        logger.error(f"❌ Error crítico en la ejecución programada: {e}")

def start_scheduler():
    # Configurar la ejecución: Todos los domingos a las 03:00 AM
    #schedule.every().sunday.at("03:00").do(job)
    schedule.every(15).minutes.do(job)
    
    logger.info("🚀 Servicio de automatización (Scheduler) iniciado correctamente.")
    logger.info("Esperando a la próxima fecha de ejecución programada...")

    # Bucle infinito que mantiene el proceso vivo y evalúa las tareas
    while True:
        schedule.run_pending()
        # Duerme 60 segundos para no consumir CPU innecesariamente
        time.sleep(60)

if __name__ == "__main__":
    # Soporte para multiprocessing (necesario por el ProcessPoolExecutor del main)
    multiprocessing.freeze_support()
    start_scheduler()