import re


def tower_name_from_screenshot_stem(stem: str) -> str:
    """Alinea el nombre de torre con el usado al leer capturas (mismo criterio que main)."""
    tower_name = re.sub(
        r"^(Map_and_Charts__|Map__)",
        "",
        stem,
        flags=re.IGNORECASE,
    )
    return tower_name.replace("_", " ").strip()
