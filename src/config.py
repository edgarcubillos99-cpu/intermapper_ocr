import os
from dotenv import load_dotenv
from pathlib import Path

# Cargar variables desde el archivo .env
load_dotenv()

class Config:
    URL = os.getenv("INTERMAPPER_URL")
    USERNAME = os.getenv("INTERMAPPER_USER")
    PASSWORD = os.getenv("INTERMAPPER_PASS")
    
    # Directorio base para el proyecto
    BASE_DIR = Path(__file__).resolve().parent.parent
    SCREENSHOT_DIR = BASE_DIR / os.getenv("SCREENSHOT_DIR", "screenshots")
    
    # Concurrencia (cuántas pestañas abriremos al mismo tiempo)
    WORKERS = int(os.getenv("CONCURRENT_WORKERS", 3))

    @classmethod
    def setup_directories(cls):
        cls.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)