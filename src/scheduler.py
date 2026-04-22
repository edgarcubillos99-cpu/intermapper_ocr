import time
import schedule
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from src.logger import get_logger
from src.main import main
from src.config import Config

logger = get_logger(__name__)

# --- INICIO SERVIDOR HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK - Agent Running")
        
    # Silenciar logs HTTP para no ensuciar la consola
    def log_message(self, format, *args):
        pass

def run_health_server():
    server = HTTPServer(('0.0.0.0', Config.APP_PORT), HealthCheckHandler)
    logger.info(f"Servidor de Health Check escuchando en el puerto {Config.APP_PORT}")
    server.serve_forever()
# --- FIN SERVIDOR HEALTH CHECK ---

def job():
    logger.info("=== INICIANDO CICLO DE EXTRACCIÓN PROGRAMADO ===")
    try:
        main()
        logger.info("=== CICLO FINALIZADO EXITOSAMENTE ===")
    except Exception as e:
        logger.error(f"Error crítico en el ciclo: {e}")

if __name__ == "__main__":
    # 1. Iniciar el servidor web ligero en un hilo en segundo plano (daemon)
    threading.Thread(target=run_health_server, daemon=True).start()

    logger.info("Iniciando el Demonio del Scheduler (Intervalo: 15 minutos)")
    
    # 2. Ejecutamos una vez inmediatamente
    job()
    
    # 3. Programamos la ejecución
    schedule.every(15).minutes.do(job)

    # Bucle infinito
    while True:
        schedule.run_pending()
        time.sleep(1)