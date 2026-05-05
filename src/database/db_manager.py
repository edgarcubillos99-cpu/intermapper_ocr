import re
from difflib import SequenceMatcher

import mysql.connector
from mysql.connector import Error

from src.config import Config
from src.logger import get_logger

logger = get_logger(__name__)

# Sufijos de tipo de AP en Intermapper (ePMP, Rocket, Lite…)
_TRAILING_AP_TYPE = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\s+ePMPePMP\d+L?\b",
        r"\s+ePMP\s*Force\s*(?:1000|2000|3000|4500|4600)\w*\b",
        r"\s+ePMP\s+\d{3,4}\s*L?",
        r"\s+ePMP\s*\d{3,4}\s*L?",
        r"\s+ePMP\s*\d+L?\s*\(?OMNI\)?",
        r"\s+ePMP\s*\d+\s*OMNI\b",
        r"\s+ePMP\s*\d+\s*\(OMNI\)",
        r"\s+ePMP\s+\d+\b",
        r"\s+ePMP\s*\d+L?\b",
        r"\s+ePMPEPMP\d+L?\b",
        r"\s+EPMPePMP\d+L?\b",
        r"\s+EPMPEPMP\d+L?\b",
        r"\s+EPMP\s*Force\s*(?:1000|2000|3000|4500|4600)\w*\b",
        r"\s+EPMP\s+\d{3,4}\s*L?",
        r"\s+EPMP\s*\d{3,4}\s*L?",
        r"\s+EPMP\s*\d+L?\s*\(?OMNI\)?",
        r"\s+EPMP\s*\d+\s*OMNI\b",
        r"\s+EPMP\s*\d+\s*\(OMNI\)",
        r"\s+EPMP\s+\d+\b",
        r"\s+EPMP\s*\d+L?\b",
        r"\s+LiteAP\s*AC\b",
        r"\s+Lite\s*AC\b",
        r"\s+LiteBeam\s*5AC\b",
        r"\s+LiteBeam\s*AC\w*",
        r"\s+Rocket\s*5AC\s*Lite\b",
        r"\s+Rocket\s*5AC\b",
        r"\s+Rocket\s*AC\b",
        r"\s+Rocket\s*Lite\b",
        r"\s+Rocket\s*5AC\s*Lit\w*",
        r"\s+Mimosa\s*C5c\b",
        r"\s+Wave\s*AP\b",
        r"\s+Wave\s*60\b",
        r"\s+WAVE\s*60\b",
        r"\s+OMNI\b",
        r"\s+[A-Za-z]{3,20}\s+ePMP\s+\d+\b",
    )
)

_PARENS_END = re.compile(r"\s*\([^)]{0,160}\)\s*$", re.IGNORECASE)

_OCR_TRAILING_MODEL = re.compile(
    r"(\bOSNAP\d+[A-Z]*-[A-Z0-9]+)\s+\d{3,4}L?\s*$", re.IGNORECASE
)


class DBManager:
    def __init__(self):
        self.host = Config.DB_HOST
        self.port = Config.DB_PORT
        self.user = Config.DB_USER
        self.password = Config.DB_PASS
        self.database = Config.DB_NAME

        self._create_database_if_not_exists()
        self.init_tables()

    def _base_connect_kwargs(self):
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
        }

    def get_connection(self):
        try:
            return mysql.connector.connect(
                **self._base_connect_kwargs(),
                database=self.database,
            )
        except Error as e:
            logger.error(f"Error conectando a MySQL: {e}")
            return None

    def _create_database_if_not_exists(self):
        try:
            conn = mysql.connector.connect(**self._base_connect_kwargs())
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
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS torres (
                    nombre VARCHAR(150) PRIMARY KEY,
                    latitud VARCHAR(50),
                    longitud VARCHAR(50),
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS submapas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    torre_nombre VARCHAR(150) UNIQUE NOT NULL,
                    ruta_imagen VARCHAR(255) NOT NULL,
                    fecha_captura TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (torre_nombre) REFERENCES torres(nombre) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dispositivos_ap (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    torre_nombre VARCHAR(150) NOT NULL,
                    ap_name VARCHAR(150) NOT NULL,
                    tipo VARCHAR(50),
                    azimut VARCHAR(50),
                    tilt VARCHAR(50),
                    altura VARCHAR(50),
                    ip_address VARCHAR(45) NULL DEFAULT NULL,
                    fecha_extraccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_ap_per_tower (torre_nombre, ap_name),
                    FOREIGN KEY (torre_nombre) REFERENCES torres(nombre) ON DELETE CASCADE
                )
            """)
            cursor.execute("SHOW COLUMNS FROM dispositivos_ap LIKE %s", ("ip_address",))
            if not cursor.fetchone():
                cursor.execute("""
                    ALTER TABLE dispositivos_ap
                    ADD COLUMN ip_address VARCHAR(45) NULL DEFAULT NULL AFTER altura
                """)
            
            cursor.execute("""
                CREATE OR REPLACE VIEW view_inventario_completo AS
                SELECT 
                    t.nombre AS torre,
                    a.ap_name AS dispositivo_ap,
                    a.tipo,
                    a.azimut,
                    a.tilt,
                    a.altura,
                    a.ip_address,
                    c.ruta_imagen AS captura_submapa,
                    a.fecha_extraccion
                FROM torres t
                LEFT JOIN dispositivos_ap a ON t.nombre = a.torre_nombre
                    LEFT JOIN submapas c ON t.nombre = c.torre_nombre;
            """)

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

    def save_site_data(self, tower_name: str, screenshot_path: str, devices: list, coords: tuple):
        lat, lon = coords
        conn = self.get_connection()
        if not conn: return

        try:
            cursor = conn.cursor()
            conn.start_transaction()

            cursor.execute("""
            INSERT INTO torres (nombre, latitud, longitud) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            latitud = VALUES(latitud), 
            longitud = VALUES(longitud)
            """, (tower_name, lat, lon))

            cursor.execute("""
                INSERT INTO submapas (torre_nombre, ruta_imagen) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE 
                ruta_imagen = VALUES(ruta_imagen), 
                fecha_captura = CURRENT_TIMESTAMP
            """, (tower_name, str(screenshot_path)))

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

    @staticmethod
    def _strip_ap_type_suffix(raw: str) -> str:
        s = (raw or "").strip()
        for _ in range(24):
            t = _PARENS_END.sub("", s).strip()
            if t != s:
                s = t
                continue
            prev = s
            for rx in _TRAILING_AP_TYPE:
                s = rx.sub("", s).strip()
            if s == prev:
                break
        s = _OCR_TRAILING_MODEL.sub(r"\1", s).strip()
        return s

    @staticmethod
    def _norm_for_ip_match(s: str) -> str:
        return " ".join(DBManager._strip_ap_type_suffix(s).lower().split())

    @staticmethod
    def _split_osnap_name_type(raw_label: str) -> tuple[str, str]:
        """Separa el nombre exacto del tipo basado en el HTML."""
        m = re.match(r"^(OSNAP[^\s]+)\s+(.+)$", raw_label.strip(), re.IGNORECASE)
        if m:
            return m.group(1).upper(), m.group(2).strip()
        return raw_label.strip().upper(), "DESCONOCIDO"

    def apply_scraped_ip_addresses(
        self, torre_nombre: str, name_ip_pairs: list[tuple[str, str]]
    ):
        conn = self.get_connection()
        if not conn or not name_ip_pairs:
            return

        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, ap_name FROM dispositivos_ap WHERE torre_nombre = %s",
                (torre_nombre,),
            )
            rows: list[tuple[int, str]] = list(cursor.fetchall())
            if not rows:
                logger.info(f"[{torre_nombre}] No hay APs en BD para asociar IPs.")
                return

            used_ids: set[int] = set()
            pending = list(name_ip_pairs)

            # --- Paso 1: exactas (nombres sin sufijo de tipo) ---
            for im_name, ip in list(pending):
                # Extraemos Nombre Puro y Tipo del HTML
                clean_name, clean_type = self._split_osnap_name_type(im_name)
                
                n_im = self._norm_for_ip_match(im_name)
                for rid, db_name in rows:
                    if rid in used_ids:
                        continue
                    if self._norm_for_ip_match(db_name) == n_im:
                        # UPDATE CORREGIDO: Actualiza Nombre, Tipo e IP
                        cursor.execute(
                            """
                            UPDATE dispositivos_ap
                            SET ip_address = %s, tipo = %s, ap_name = %s
                            WHERE id = %s
                            """,
                            (ip, clean_type, clean_name, rid),
                        )
                        used_ids.add(rid)
                        pending.remove((im_name, ip))
                        logger.info(f"[{torre_nombre}] Corrección Exacta: OCR '{db_name}' -> HTML '{clean_name}' | Tipo: {clean_type} | IP: {ip}")
                        break

            # --- Paso 2: difuso ---
            fuzzy_min = 0.78
            remaining_rows = [(rid, dbn) for rid, dbn in rows if rid not in used_ids]

            for im_name, ip in list(pending):
                clean_name, clean_type = self._split_osnap_name_type(im_name)
                
                n_im = self._norm_for_ip_match(im_name)
                best: tuple[float, int, str] | None = None
                for rid, db_name in remaining_rows:
                    n_db = self._norm_for_ip_match(db_name)
                    r = SequenceMatcher(None, n_im, n_db).ratio()
                    if not best or r > best[0]:
                        best = (r, rid, db_name)

                if not best or best[0] < fuzzy_min:
                    logger.warning(
                        f"[{torre_nombre}] Sin fila para Intermapper {im_name!r} (mejor ratio {best[0] if best else 0:.2f})"
                    )
                    continue

                _, rid, db_name = best
                try:
                    # UPDATE CORREGIDO: Actualiza Nombre, Tipo e IP
                    cursor.execute(
                        """
                        UPDATE dispositivos_ap
                        SET ap_name = %s, tipo = %s, ip_address = %s
                        WHERE id = %s
                        """,
                        (clean_name, clean_type, ip, rid),
                    )
                    remaining_rows = [x for x in remaining_rows if x[0] != rid]
                    used_ids.add(rid)
                    pending.remove((im_name, ip))
                    logger.info(f"[{torre_nombre}] Corrección Difusa: OCR '{db_name}' -> HTML '{clean_name}' | Tipo: {clean_type} | IP: {ip}")
                except Error as e:
                    if getattr(e, "errno", None) == 1062:
                        cursor.execute(
                            """
                            UPDATE dispositivos_ap
                            SET ip_address = %s, tipo = %s
                            WHERE torre_nombre = %s AND ap_name = %s
                            """,
                            (ip, clean_type, torre_nombre, clean_name),
                        )
                        remaining_rows = [x for x in remaining_rows if x[0] != rid]
                        used_ids.add(rid)
                        pending.remove((im_name, ip))
                        logger.warning(
                            f"[{torre_nombre}] Nombre {clean_name!r} ya existía; IPs y Tipo actualizados."
                        )
                    else:
                        raise

            conn.commit()
        except Error as e:
            conn.rollback()
            logger.error(f"Error aplicando IPs para {torre_nombre}: {e}")
        finally:
            cursor.close()
            conn.close()