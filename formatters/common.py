"""
Shared low-level helpers used across multiple formatter domains.
"""


def wind_direction_ru(deg: float) -> str:
    """Переводит градусы направления ветра в русское направление."""
    directions = [
        "северный",
        "северо-восточный",
        "восточный",
        "юго-восточный",
        "южный",
        "юго-западный",
        "западный",
        "северо-западный",
    ]
    index = round(deg / 45) % 8
    return directions[index]


def _wind_text_from_values(wind_speed: float | None, wind_deg: float | None) -> str:
    """Собирает строку с ветром для ответов."""
    if wind_speed is None:
        return "н/д"
    if wind_deg is None:
        return f"{wind_speed} м/с"
    return f"{wind_speed} м/с, {wind_direction_ru(wind_deg)}"
