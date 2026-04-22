import re


def parse_coordinates(text: str) -> tuple[float, float] | None:
    """
    Парсит координаты из строки в форматах:
    - "55.5789, 37.9051"
    - "55.5789 37.9051"
    """
    raw = (text or "").strip().replace(";", ",")
    if not raw:
        return None

    normalized = re.sub(r"\s+", " ", raw)
    if "," in normalized:
        parts = [part.strip() for part in normalized.split(",") if part.strip()]
    else:
        parts = normalized.split(" ")

    if len(parts) != 2:
        return None

    try:
        lat = float(parts[0].replace(",", "."))
        lon = float(parts[1].replace(",", "."))
    except ValueError:
        return None

    if not (-90 <= lat <= 90):
        return None
    if not (-180 <= lon <= 180):
        return None

    return lat, lon
