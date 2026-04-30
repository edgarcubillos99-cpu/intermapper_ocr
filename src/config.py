import os
from dotenv import load_dotenv
from pathlib import Path

# Cargar variables desde el archivo .env
load_dotenv()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)


class Config:

    APP_PORT = os.getenv("APP_PORT", 8080)
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = _int_env("DB_PORT", 3306)
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASS = os.getenv("DB_PASS", "")
    DB_NAME = os.getenv("DB_NAME", "intermapper_db")
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