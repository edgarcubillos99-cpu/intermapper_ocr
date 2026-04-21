import time
import schedule
from src.logger import get_logger
from src.main import main  # Tu función principal que orquesta todo

logger = get_logger(__name__)

def job():
    logger.info("=== INICIANDO CICLO DE EXTRACCIÓN PROGRAMADO ===")
    try:
        main()
        logger.info("=== CICLO FINALIZADO EXITOSAMENTE ===")
    except Exception as e:
        logger.error(f"Error crítico en el ciclo: {e}")

if __name__ == "__main__":
    logger.info("Iniciando el Demonio del Scheduler (Intervalo: 15 minutos)")
    
    # Ejecutamos una vez inmediatamente al levantar el contenedor
    job()
    
    # Programamos la ejecución cada 15 minutos
    schedule.every(15).minutes.do(job)

    # Bucle infinito para mantener vivo el contenedor
    while True:
        schedule.run_pending()
        time.sleep(1)