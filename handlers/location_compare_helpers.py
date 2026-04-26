from datetime import datetime
from math import asin, cos, radians, sin, sqrt


def _ai_compare_current_payload(city_label: str, weather: dict, *, location_meta: dict | None = None) -> dict:
    """Собирает payload текущей погоды для AI-сравнения."""
    main_data = weather.get("main", {}) if isinstance(weather, dict) else {}
    weather_item = weather.get("weather", [{}])[0] if isinstance(weather, dict) else {}
    wind_data = weather.get("wind", {}) if isinstance(weather, dict) else {}
    meta = location_meta if isinstance(location_meta, dict) else {}
    return {
        "city_label": city_label,
        "lat": meta.get("lat"),
        "lon": meta.get("lon"),
        "country": meta.get("country"),
        "state": meta.get("state"),
        "temperature": main_data.get("temp"),
        "feels_like": main_data.get("feels_like"),
        "description": weather_item.get("description"),
        "humidity": main_data.get("humidity"),
        "wind_speed": wind_data.get("speed"),
    }


def _format_number(value: object, suffix: str = "") -> str:
    """Форматирует числовое значение для краткой текстовой сводки."""
    if isinstance(value, (int, float)):
        return f"{float(value):.1f}{suffix}"
    return "н/д"


def _ai_compare_day_payload(
    city_label: str,
    selected_day: str,
    day_items: list[dict],
    *,
    location_meta: dict | None = None,
) -> dict:
    """Собирает payload выбранного дня прогноза для AI-сравнения."""
    temps: list[float] = []
    desc_counter: dict[str, int] = {}
    rain_slots = 0
    intervals: list[str] = []
    max_pop = 0.0
    wind_speeds: list[float] = []

    for item in day_items:
        if not isinstance(item, dict):
            continue
        main_data = item.get("main", {}) if isinstance(item.get("main"), dict) else {}
        temp = main_data.get("temp")
        if isinstance(temp, (int, float)):
            temps.append(float(temp))

        weather_item = item.get("weather", [{}])[0] if isinstance(item.get("weather"), list) else {}
        description = str(weather_item.get("description") or "без описания")
        desc_counter[description] = desc_counter.get(description, 0) + 1
        desc_l = description.lower()
        if any(x in desc_l for x in ("дожд", "лив", "гроза", "снег")):
            rain_slots += 1

        pop_raw = item.get("pop")
        if isinstance(pop_raw, (int, float)):
            max_pop = max(max_pop, float(pop_raw))

        wind_data = item.get("wind", {}) if isinstance(item.get("wind"), dict) else {}
        wind_speed = wind_data.get("speed")
        if isinstance(wind_speed, (int, float)):
            wind_speeds.append(float(wind_speed))

        dt_txt = str(item.get("dt_txt") or "")
        if " " in dt_txt:
            time_part = dt_txt.split(" ")[1][:5]
            intervals.append(time_part)

    dominant_description = max(desc_counter, key=desc_counter.get) if desc_counter else "без описания"
    meta = location_meta if isinstance(location_meta, dict) else {}
    return {
        "city_label": city_label,
        "lat": meta.get("lat"),
        "lon": meta.get("lon"),
        "country": meta.get("country"),
        "state": meta.get("state"),
        "selected_day": selected_day,
        "min_temp": min(temps) if temps else None,
        "max_temp": max(temps) if temps else None,
        "dominant_description": dominant_description,
        "precipitation_signal": {
            "rain_slots": rain_slots,
            "max_pop": max_pop,
        },
        "wind_signal": {
            "avg_speed": (sum(wind_speeds) / len(wind_speeds)) if wind_speeds else None,
            "max_speed": max(wind_speeds) if wind_speeds else None,
        },
        "key_day_intervals": intervals[:6],
    }


def _format_precipitation_summary(payload: dict) -> str:
    """Формирует естественный краткий текст про осадки для day-summary."""
    signal = payload.get("precipitation_signal") if isinstance(payload, dict) else {}
    max_pop_raw = signal.get("max_pop") if isinstance(signal, dict) else None
    max_pop = float(max_pop_raw) if isinstance(max_pop_raw, (int, float)) else None
    description = str(payload.get("dominant_description") or "").strip().lower()

    has_snow = "снег" in description
    has_rain = any(x in description for x in ("дожд", "лив", "гроза"))

    if max_pop is None:
        if has_snow:
            return "возможен снег"
        if has_rain:
            return "возможен дождь"
        return "без существенных осадков"

    if max_pop < 0.2:
        if has_snow:
            return "снег маловероятен"
        if has_rain:
            return "дождь маловероятен"
        return "без существенных осадков"
    if max_pop < 0.5:
        if has_snow:
            return "местами возможен снег"
        if has_rain:
            return "местами возможен дождь"
        return "возможны осадки"
    if max_pop < 0.8:
        if has_snow:
            return "возможен снег"
        if has_rain:
            return "возможен дождь"
        return "возможны осадки"
    if has_snow:
        return "высокий шанс снега"
    if has_rain:
        return "высокий шанс дождя"
    return "высокий шанс осадков"


def format_ai_compare_day_summary(payload: dict) -> str:
    """Краткая дневная сводка по одной локации для сценария compare by date."""
    min_temp = _format_number(payload.get("min_temp"), "°C")
    max_temp = _format_number(payload.get("max_temp"), "°C")
    description = str(payload.get("dominant_description") or "").strip()
    wind_signal = payload.get("wind_signal") if isinstance(payload, dict) else {}
    avg_wind = wind_signal.get("avg_speed") if isinstance(wind_signal, dict) else None
    max_wind = wind_signal.get("max_speed") if isinstance(wind_signal, dict) else None
    precip = _format_precipitation_summary(payload)

    lines = [f"• температура: от {min_temp} до {max_temp}"]
    if description:
        lines.append(f"• условия: {description}")
    if isinstance(avg_wind, (int, float)) and isinstance(max_wind, (int, float)):
        lines.append(f"• ветер: в среднем {_format_number(avg_wind, ' м/с')}, порывы до {_format_number(max_wind, ' м/с')}")
    elif isinstance(avg_wind, (int, float)):
        lines.append(f"• ветер: в среднем {_format_number(avg_wind, ' м/с')}")
    elif isinstance(max_wind, (int, float)):
        lines.append(f"• ветер: до {_format_number(max_wind, ' м/с')}")
    lines.append(f"• осадки: {precip}")
    return "\n".join(lines)


def format_ai_compare_day_summary_message(payload: dict, selected_day: str, location_index: int) -> str:
    """Возвращает детерминированную карточку сводки для конкретной локации."""
    city = str(payload.get("city_label") or f"Локация {location_index}")
    return (
        f"📍 Локация {location_index}: {city}\n"
        f"Сводка на {selected_day}:\n"
        f"{format_ai_compare_day_summary(payload)}"
    )


def normalize_location_name(value: object) -> str:
    """Нормализует имя локации для fallback-сравнения без координат."""
    text = str(value or "").strip().lower().replace("ё", "е")
    text = " ".join(text.split())
    # Убираем служебные префиксы из сохранённых названий вида «Дом — Тольятти».
    if "—" in text:
        text = text.split("—")[-1].strip()
    return text


def calculate_distance_km(lat_1: float, lon_1: float, lat_2: float, lon_2: float) -> float:
    """Считает расстояние по формуле гаверсинусов."""
    earth_radius_km = 6371.0
    d_lat = radians(lat_2 - lat_1)
    d_lon = radians(lon_2 - lon_1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat_1)) * cos(radians(lat_2)) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return earth_radius_km * c


def is_same_location(loc_1: dict, loc_2: dict, *, distance_threshold_km: float = 2.5) -> bool:
    """Проверяет, что две локации по сути одинаковые."""
    lat_1 = loc_1.get("lat")
    lon_1 = loc_1.get("lon")
    lat_2 = loc_2.get("lat")
    lon_2 = loc_2.get("lon")
    if all(isinstance(v, (int, float)) for v in (lat_1, lon_1, lat_2, lon_2)):
        distance_km = calculate_distance_km(float(lat_1), float(lon_1), float(lat_2), float(lon_2))
        if distance_km < distance_threshold_km:
            return True

    name_1 = normalize_location_name(loc_1.get("city_label"))
    name_2 = normalize_location_name(loc_2.get("city_label"))
    country_1 = normalize_location_name(loc_1.get("country"))
    country_2 = normalize_location_name(loc_2.get("country"))
    state_1 = normalize_location_name(loc_1.get("state"))
    state_2 = normalize_location_name(loc_2.get("state"))

    if name_1 and name_2 and name_1 == name_2:
        if country_1 and country_2 and country_1 != country_2:
            return False
        if state_1 and state_2 and state_1 != state_2:
            return False
        return True
    return False


def validate_second_compare_location(loc_1: dict, loc_2: dict) -> str | None:
    """Валидирует вторую локацию compare-сценария относительно первой."""
    if is_same_location(loc_1, loc_2):
        return "duplicate"
    return None


def _sorted_day_keys(day_keys: set[str]) -> list[str]:
    """Сортирует ключи дней DD.MM по календарному порядку внутри года."""

    def _to_date(value: str) -> datetime:
        return datetime.strptime(value, "%d.%m")

    try:
        return sorted(day_keys, key=_to_date)
    except Exception:
        return sorted(day_keys)

