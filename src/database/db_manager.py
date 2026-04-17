import mysql.connector
from mysql.connector import Error
from src.config import Config
from src.logger import get_logger

logger = get_logger(__name__)

class DBManager:
    def __init__(self):
        self.host = Config.DB_HOST
        self.user = Config.DB_USER
        self.password = Config.DB_PASS
        self.database = Config.DB_NAME
        
        # 1. Crear la DB si no existe antes de conectarnos a ella
        self._create_database_if_not_exists()
        self.init_tables()

    def get_connection(self):
        """Retorna una nueva conexión a la base de datos."""
        try:
            return mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
        except Error as e:
            logger.error(f"Error conectando a MySQL: {e}")
            return None

    def _create_database_if_not_exists(self):
        try:
            conn = mysql.connector.connect(host=self.host, user=self.user, password=self.password)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            cursor.close()
            conn.close()
        except Error as e:
            logger.error(f"Error creando la base de datos: {e}")

    def init_tables(self):
        """Crea las 3 tablas normalizadas si no existen."""
        conn = self.get_connection()
        if not conn: return

        try:
            cursor = conn.cursor()
            
            # Tabla 1: Maestro de Torres
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS torres (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(150) UNIQUE NOT NULL,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tabla 2: Capturas de pantalla
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS capturas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    torre_id INT NOT NULL,
                    ruta_imagen VARCHAR(255) NOT NULL,
                    fecha_captura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (torre_id) REFERENCES torres(id) ON DELETE CASCADE
                )
            """)

            # Tabla 3: Dispositivos AP
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dispositivos_ap (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    torre_id INT NOT NULL,
                    ap_name VARCHAR(150) NOT NULL,
                    tipo VARCHAR(50),
                    azimut VARCHAR(50),
                    tilt VARCHAR(50),
                    altura VARCHAR(50),
                    fecha_extraccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (torre_id) REFERENCES torres(id) ON DELETE CASCADE
                )
            """)
            
            conn.commit()
            logger.info("✅ Tablas de la base de datos inicializadas correctamente.")
            
        except Error as e:
            logger.error(f"Error inicializando tablas: {e}")
        finally:
            cursor.close()
            conn.close()

    def save_site_data(self, tower_name: str, screenshot_path: str, devices: list):
        """
        Guarda toda la información de un site en una sola transacción.
        """
        conn = self.get_connection()
        if not conn: return

        try:
            cursor = conn.cursor()
            # Iniciar transacción
            conn.start_transaction()

            # 1. Insertar o recuperar ID de la torre
            cursor.execute(
                "INSERT IGNORE INTO torres (nombre) VALUES (%s)", 
                (tower_name,)
            )
            cursor.execute("SELECT id FROM torres WHERE nombre = %s", (tower_name,))
            torre_id = cursor.fetchone()[0]

            # 2. Insertar registro de la captura
            cursor.execute(
                "INSERT INTO capturas (torre_id, ruta_imagen) VALUES (%s, %s)",
                (torre_id, str(screenshot_path))
            )

            # 3. Insertar todos los dispositivos AP
            if devices:
                # Preparamos la data eliminando la clave 'Torre' ya que usamos el torre_id
                ap_data = [
                    (torre_id, ap['AP_Name'], ap['Tipo'], ap['Azimut'], ap['Tilt'], ap['Altura'])
                    for ap in devices
                ]
                
                query_aps = """
                    INSERT INTO dispositivos_ap 
                    (torre_id, ap_name, tipo, azimut, tilt, altura) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.executemany(query_aps, ap_data)

            # Confirmar transacción
            conn.commit()
            logger.info(f"💾 Datos guardados en BD para la torre: {tower_name}")

        except Error as e:
            conn.rollback() # Si algo falla, deshacemos todos los inserts
            logger.error(f"Error guardando datos en BD. Transacción revertida: {e}")
        finally:
            cursor.close()
            conn.close()