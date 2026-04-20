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
        
        self._create_database_if_not_exists()
        self.init_tables()

    def get_connection(self):
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
        conn = self.get_connection()
        if not conn: return

        try:
            cursor = conn.cursor()
            
            # 1. Maestro de Torres (Ahora el 'nombre' es la Llave Primaria)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS torres (
                    nombre VARCHAR(150) PRIMARY KEY,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Capturas de los Submapas (Relacionado por el nombre de la torre)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS submapas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    torre_nombre VARCHAR(150) UNIQUE NOT NULL,
                    ruta_imagen VARCHAR(255) NOT NULL,
                    fecha_captura TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (torre_nombre) REFERENCES torres(nombre) ON DELETE CASCADE
                )
            """)

            # 3. Dispositivos AP (Ahora contiene el torre_nombre directamente)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dispositivos_ap (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    torre_nombre VARCHAR(150) NOT NULL,
                    ap_name VARCHAR(150) NOT NULL,
                    tipo VARCHAR(50),
                    azimut VARCHAR(50),
                    tilt VARCHAR(50),
                    altura VARCHAR(50),
                    fecha_extraccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_ap_per_tower (torre_nombre, ap_name),
                    FOREIGN KEY (torre_nombre) REFERENCES torres(nombre) ON DELETE CASCADE
                )
            """)
            
            # Vista 1: Inventario Completo
            cursor.execute("""
                CREATE OR REPLACE VIEW view_inventario_completo AS
                SELECT 
                    t.nombre AS torre,
                    a.ap_name AS dispositivo_ap,
                    a.tipo,
                    a.azimut,
                    a.tilt,
                    a.altura,
                    c.ruta_imagen AS captura_submapa,
                    a.fecha_extraccion
                FROM torres t
                LEFT JOIN dispositivos_ap a ON t.nombre = a.torre_nombre
                LEFT JOIN capturas c ON t.nombre = c.torre_nombre;
            """)

            # Vista 2: Resumen agrupado
            cursor.execute("""
                CREATE OR REPLACE VIEW view_resumen_torres AS
                SELECT 
                    t.nombre AS torre,
                    COUNT(a.id) AS cantidad_aps,
                    GROUP_CONCAT(a.ap_name SEPARATOR ', ') AS lista_de_aps
                FROM torres t
                LEFT JOIN dispositivos_ap a ON t.nombre = a.torre_nombre
                GROUP BY t.nombre;
            """)
            
            conn.commit()
            logger.info("✅ Tablas inicializadas con Clave Natural (torre_nombre).")
        except Error as e:
            logger.error(f"Error inicializando tablas: {e}")
        finally:
            cursor.close()
            conn.close()

    def save_site_data(self, tower_name: str, screenshot_path: str, devices: list):
        conn = self.get_connection()
        if not conn: return

        try:
            cursor = conn.cursor()
            conn.start_transaction()

            # 1. Insertar Torre
            cursor.execute("INSERT IGNORE INTO torres (nombre) VALUES (%s)", (tower_name,))

            # 2. Insertar o Actualizar Captura (Usando tower_name directo)
            cursor.execute("""
                INSERT INTO capturas (torre_nombre, ruta_imagen) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE 
                ruta_imagen = VALUES(ruta_imagen), 
                fecha_captura = CURRENT_TIMESTAMP
            """, (tower_name, str(screenshot_path)))

            # 3. Insertar o Actualizar Dispositivos AP (Usando tower_name directo)
            if devices:
                ap_data = [
                    (tower_name, ap['AP_Name'], ap['Tipo'], ap['Azimut'], ap['Tilt'], ap['Altura'])
                    for ap in devices
                ]
                
                query_aps = """
                    INSERT INTO dispositivos_ap 
                    (torre_nombre, ap_name, tipo, azimut, tilt, altura) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    tipo = VALUES(tipo),
                    azimut = VALUES(azimut),
                    tilt = VALUES(tilt),
                    altura = VALUES(altura),
                    fecha_extraccion = CURRENT_TIMESTAMP
                """
                cursor.executemany(query_aps, ap_data)

            conn.commit()
            logger.info(f"💾 Datos y captura actualizados en BD para la torre: {tower_name}")

        except Error as e:
            conn.rollback()
            logger.error(f"Error en BD, revirtiendo: {e}")
        finally:
            cursor.close()
            conn.close()