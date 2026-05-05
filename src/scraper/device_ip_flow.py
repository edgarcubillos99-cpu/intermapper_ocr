import asyncio
import re
from urllib.parse import urljoin

from playwright.async_api import BrowserContext

from src.config import Config
from src.logger import get_logger

logger = get_logger(__name__)

# --- NUEVA FUNCIÓN DE SEPARACIÓN ---
def _split_osnap_name_type(raw_label: str) -> tuple[str, str]:
    """
    Separa 'OSNAP45-B ePMP2000' en ('OSNAP45-B', 'ePMP2000').
    Captura todo lo que empiece por OSNAP sin espacios como nombre, 
    y el resto como tipo.
    """
    m = re.match(r"^(OSNAP[^\s]+)\s+(.+)$", raw_label.strip(), re.IGNORECASE)
    if m:
        return m.group(1).upper(), m.group(2).strip()
    return raw_label.strip().upper(), "DESCONOCIDO"
# -----------------------------------

_GOTO_MS = 120_000

_ADDRESS_RE = re.compile(
    r"Address:\s*(\d{1,3}(?:\.\d{1,3}){3})",
    re.IGNORECASE | re.DOTALL,
)

def _extract_ip_from_status_text(text: str) -> str | None:
    if not text:
        return None
    m = _ADDRESS_RE.search(text)
    return m.group(1).strip() if m else None

def _is_osnap_device_name(name: str) -> bool:
    return "osnap" in name.lower()

async def _discover_osnap_device_links(
    context: BrowserContext, sem: asyncio.Semaphore, submap_url: str
) -> list[tuple[str, str]]:
    """Descubre los enlaces desde el Device List."""
    async with sem:
        page = await context.new_page()
        try:
            await page.goto(submap_url, wait_until="load", timeout=_GOTO_MS)
            await asyncio.sleep(1)

            dev_list = page.locator('nav a[href*="device_list"]').filter(has_text="Device List").first
            try:
                async with page.expect_navigation(wait_until="load", timeout=min(_GOTO_MS, 60_000)):
                    await dev_list.click()
            except Exception:
                await dev_list.click()

            table = page.locator('table:has(th:text-is("Name"))').first
            await table.wait_for(state="visible", timeout=_GOTO_MS)
            await table.locator("tr:has(td a)").first.wait_for(state="visible", timeout=_GOTO_MS)
            await asyncio.sleep(0.6)

            body_rows = table.locator("tbody tr")
            n_body = await body_rows.count()
            rows = body_rows if n_body > 0 else table.locator("tr")

            seen_device_urls: set[str] = set()
            to_visit: list[tuple[str, str]] = []

            n = await rows.count()
            for i in range(n):
                row = rows.nth(i)
                if await row.locator("th").count() > 0:
                    continue
                link = row.locator("td a").first
                if await link.count() == 0:
                    continue
                label = (await link.inner_text()).strip()
                if not _is_osnap_device_name(label):
                    continue
                href = await link.get_attribute("href")
                if not href or href.startswith("#") or href.lower().startswith("javascript:"):
                    continue
                full = urljoin(page.url, href)
                if full in seen_device_urls:
                    continue
                seen_device_urls.add(full)
                to_visit.append((full, label))

            return to_visit
        finally:
            await page.close()


async def _fetch_address_for_device(
    context: BrowserContext,
    sem: asyncio.Semaphore,
    device_url: str,
    display_name: str,
) -> dict | None:
    """Extrae la IP y retorna el paquete de datos limpio."""
    async with sem:
        page = await context.new_page()
        try:
            await page.goto(device_url, wait_until="load", timeout=_GOTO_MS)
            sw = page.locator("pre#swpre")
            try:
                await sw.first.wait_for(state="attached", timeout=45_000)
                await page.wait_for_function(
                    """() => {
                        const p = document.querySelector('pre#swpre');
                        if (!p) return false;
                        const t = p.innerText || '';
                        return /Address:\\s*[\\d.]/.test(t);
                    }""",
                    timeout=45_000,
                )
            except Exception:
                pass
            await asyncio.sleep(0.25)

            text = ""
            if await sw.count() > 0:
                text = await sw.first.inner_text()
            ip = _extract_ip_from_status_text(text)
            if not ip:
                ip = _extract_ip_from_status_text(await page.locator("body").inner_text())
            if not ip:
                logger.warning(f"Sin Address parseable para {display_name} en {device_url}")
                return None
            
            # --- SEPARAMOS NOMBRE Y TIPO AQUÍ ---
            ap_name, ap_type = _split_osnap_name_type(display_name)
            logger.info(f"Leído: {ap_name} | Tipo: {ap_type} | IP: {ip}")
            
            return {
                "html_name": ap_name,
                "html_type": ap_type,
                "ip_address": ip
            }
            
        except Exception as e:
            logger.error(f"Error leyendo dispositivo {display_name}: {e}")
            return None
        finally:
            await page.close()


async def collect_osnap_addresses_from_submap(
    context: BrowserContext, sem: asyncio.Semaphore, submap_url: str
) -> list[dict]:
    to_visit = await _discover_osnap_device_links(context, sem, submap_url)
    if not to_visit:
        return []

    tasks = [
        _fetch_address_for_device(context, sem, url, name)
        for url, name in to_visit
    ]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for item in raw:
        if isinstance(item, Exception):
            logger.error(f"Error en worker de IP: {item}")
            continue
        if item:
            out.append(item)
    return out


async def run_device_ip_phase(site_entries: list[tuple[str, str]]):
    from src.scraper.browser import BrowserManager
    from src.scraper.navigator import IntermapperScraper

    if not site_entries:
        return

    logger.info(f"--- INICIANDO FASE 3: EXTRACCIÓN Y RECONCILIACIÓN DE DATOS ---")
    browser_manager = BrowserManager()
    context = await browser_manager.start()
    context.set_default_navigation_timeout(_GOTO_MS)
    scraper = IntermapperScraper(context)
    page = await scraper.login()
    await page.close()

    sem = asyncio.Semaphore(Config.WORKERS)

    async def one_tower(tower: str, submap_url: str):
        devices = await collect_osnap_addresses_from_submap(context, sem, submap_url)
        return tower, devices

    try:
        outcomes = await asyncio.gather(
            *[one_tower(t, u) for t, u in site_entries],
            return_exceptions=True,
        )

        from src.database.db_manager import DBManager
        db = DBManager()
        
        for item in outcomes:
            if isinstance(item, Exception):
                logger.error(f"Fase 3 error en tarea: {item}")
                continue
            tower, pairs = item
            if not pairs:
                logger.info(f"[{tower}] Sin dispositivos OSNAP en Device List.")
                continue

            # apply_scraped_ip_addresses espera (etiqueta_completa_html, ip) como en Device List
            name_ip_pairs = [
                (f"{d['html_name']} {d['html_type']}".strip(), d["ip_address"])
                for d in pairs
            ]
            db.apply_scraped_ip_addresses(tower, name_ip_pairs)
    finally:
        await browser_manager.stop()