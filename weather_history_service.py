from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from weather.open_meteo import fetch_open_meteo_history_daily, weather_code_to_description_ru


def parse_history_date_input(raw_value: str, *, today: date | None = None) -> tuple[date | None, str | None]:
    """Parses a user-entered history date and validates that it is in the past."""
    text = str(raw_value or "").strip()
    today_value = today or date.today()
    if not text:
        return None, "Не увидела дату. Введи ее в формате YYYY-MM-DD или DD.MM.YYYY."

    parsed_date: date | None = None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            parsed_date = datetime.strptime(text, fmt).date()
            break
        except ValueError:
            continue

    if parsed_date is None:
        return None, "Не получилось распознать дату. Введи ее в формате YYYY-MM-DD или DD.MM.YYYY."
    if parsed_date >= today_value:
        return None, "Нужна дата из прошлого. Введи день раньше сегодняшнего, например 2026-06-05 или 05.06.2026."
    return parsed_date, None


def resolve_history_preset_date(preset: str, *, today: date | None = None) -> date | None:
    """Returns a calendar date for a supported relative history preset."""
    today_value = today or date.today()
    delta_map = {
        "yesterday": 1,
        "7d": 7,
        "30d": 30,
    }
    delta_days = delta_map.get(str(preset or "").strip().lower())
    if delta_days is None:
        return None
    return today_value - timedelta(days=delta_days)


def format_history_date_label(target_date: date) -> str:
    """Formats a date for user-facing history messages."""
    return target_date.strftime("%d.%m.%Y")


def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _to_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _pick_daily_value(daily: dict[str, Any], key: str, *, index: int) -> object | None:
    raw = daily.get(key)
    if not isinstance(raw, list) or index < 0 or index >= len(raw):
        return None
    return raw[index]


def normalize_open_meteo_history_day(root: dict[str, Any] | None, target_date: date) -> dict[str, Any] | None:
    """Normalizes one daily row from Open-Meteo archive output into a stable internal shape."""
    if not isinstance(root, dict):
        return None
    daily = root.get("daily")
    if not isinstance(daily, dict):
        return None

    raw_times = daily.get("time")
    if not isinstance(raw_times, list) or not raw_times:
        return None

    target_iso = target_date.isoformat()
    try:
        index = raw_times.index(target_iso)
    except ValueError:
        return None

    pressure_value = _to_float(_pick_daily_value(daily, "pressure_msl_mean", index=index))
    pressure_source = "pressure_msl_mean"
    if pressure_value is None:
        pressure_value = _to_float(_pick_daily_value(daily, "surface_pressure_mean", index=index))
        pressure_source = "surface_pressure_mean"

    weather_code = _to_int(_pick_daily_value(daily, "weather_code", index=index))
    normalized = {
        "date": target_iso,
        "date_label": format_history_date_label(target_date),
        "timezone": root.get("timezone"),
        "temperature_max": _to_float(_pick_daily_value(daily, "temperature_2m_max", index=index)),
        "temperature_min": _to_float(_pick_daily_value(daily, "temperature_2m_min", index=index)),
        "temperature_mean": _to_float(_pick_daily_value(daily, "temperature_2m_mean", index=index)),
        "precipitation_sum": _to_float(_pick_daily_value(daily, "precipitation_sum", index=index)),
        "rain_sum": _to_float(_pick_daily_value(daily, "rain_sum", index=index)),
        "snowfall_sum": _to_float(_pick_daily_value(daily, "snowfall_sum", index=index)),
        "wind_speed_max": _to_float(_pick_daily_value(daily, "wind_speed_10m_max", index=index)),
        "wind_direction_dominant": _to_float(_pick_daily_value(daily, "wind_direction_10m_dominant", index=index)),
        "relative_humidity_mean": _to_float(_pick_daily_value(daily, "relative_humidity_2m_mean", index=index)),
        "pressure_mean": pressure_value,
        "pressure_source": pressure_source if pressure_value is not None else None,
        "weather_code": weather_code,
        "weather_description": weather_code_to_description_ru(weather_code) if weather_code is not None else None,
    }
    return normalized


def get_weather_history_by_date(lat: float, lon: float, city_label: str, target_date: date) -> dict[str, Any]:
    """Fetches archived day-level weather data and returns a normalized result payload."""
    root = fetch_open_meteo_history_daily(float(lat), float(lon), target_date=target_date)
    if not isinstance(root, dict):
        return {
            "ok": False,
            "error_code": "history_unavailable",
            "error_message": "Не удалось получить архивную погоду. Попробуй позже.",
            "city_label": city_label,
            "history": None,
        }

    normalized = normalize_open_meteo_history_day(root, target_date)
    if not isinstance(normalized, dict):
        return {
            "ok": False,
            "error_code": "history_invalid_payload",
            "error_message": "Не удалось разобрать архивные данные за эту дату. Попробуй выбрать другой день.",
            "city_label": city_label,
            "history": None,
        }

    return {
        "ok": True,
        "error_code": None,
        "error_message": None,
        "city_label": city_label,
        "history": normalized,
    }
