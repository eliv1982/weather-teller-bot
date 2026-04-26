def normalize_weather_description(description: object) -> str:
    """Normalizes user-facing weather wording without changing raw weather payloads."""
    if description is None:
        return ""

    text = " ".join(str(description).strip().split())
    if not text:
        return ""

    lowered = text.lower()
    replacements = {
        "небольшой проливной дождь": "небольшой кратковременный дождь",
        "небольшой ливневый дождь": "небольшой кратковременный дождь",
        "легкий проливной дождь": "кратковременный дождь",
        "лёгкий проливной дождь": "кратковременный дождь",
        "проливной дождь": "сильный дождь",
    }
    return replacements.get(lowered, text)

