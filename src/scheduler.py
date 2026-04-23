import time
import schedule
import threading
import os
from http.server import SimpleHTTPRequestHandler, HTTPServer
from src.logger import get_logger
from src.main import main
from src.config import Config

logger = get_logger(__name__)

# --- INICIO SERVIDOR HEALTH CHECK Y ARCHIVOS ---
class ImageAndHealthHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Apuntamos el servidor para que sirva archivos desde la carpeta de capturas
        super().__init__(*args, directory=str(Config.SCREENSHOT_DIR), **kwargs)

    def do_GET(self):
        # Si la petición es exactamente a la raíz o a un endpoint de health
        if self.path == '/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK - Agent Running")
        else:
            # Si piden cualquier otra ruta (ej: /torre_principal.png), servimos la imagen
            try:
                super().do_GET()
            except Exception as e:
                self.send_error(404, "File not found")

    def log_message(self, format, *args):
        # Silenciar logs HTTP exitosos (200) para no ensuciar la consola, 
        # pero registrar errores (como 404)
        if args[1] != '200': 
            super().log_message(format, *args)

def run_server():
    # Asegurar que el directorio de capturas existe antes de levantar el servidor
    Config.setup_directories()
    # Asegurar que el puerto es un entero
    port = int(Config.APP_PORT)
    server = HTTPServer(('0.0.0.0', port), ImageAndHealthHandler)
    logger.info(f"Servidor HTTP (Health y Archivos) escuchando en el puerto {port}")
    server.serve_forever()
# --- FIN SERVIDOR HEALTH CHECK Y ARCHIVOS ---

def job():
    logger.info("=== INICIANDO CICLO DE EXTRACCIÓN PROGRAMADO ===")
    try:
        main()
        logger.info("=== CICLO FINALIZADO EXITOSAMENTE ===")
    except Exception as e:
        logger.error(f"Error crítico en el ciclo: {e}")

if __name__ == "__main__":
    # 1. Iniciar el servidor web en un hilo en segundo plano (daemon)
    threading.Thread(target=run_server, daemon=True).start()

    logger.info("Iniciando el Demonio del Scheduler (Intervalo: 1 semana)")
    
    # 2. Ejecutamos una vez inmediatamente
    job()
    
    # 3. Programamos la ejecución
    schedule.every(1).week.do(job)

    # Bucle infinito
    while True:
        schedule.run_pending()
        time.sleep(1)