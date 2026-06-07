from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from utils.date_parsing import parse_calendar_date, parse_day_first_short_year_date
from weather.open_meteo import fetch_open_meteo_history_daily, weather_code_to_description_ru


@dataclass(frozen=True)
class HistoryDateResolution:
    parsed_date: date | None
    error_message: str | None
    clarification_dates: list[date]


def parse_history_date_input(raw_value: str, *, today: date | None = None) -> tuple[date | None, str | None]:
    """Parses a user-entered history date and validates that it is in the past."""
    resolution = resolve_history_date_input(raw_value, today=today)
    if resolution.clarification_dates:
        return None, "Нужно уточнить год."
    return resolution.parsed_date, resolution.error_message


def resolve_history_date_input(raw_value: str, *, today: date | None = None) -> HistoryDateResolution:
    """Parses a user-entered history date and optionally returns year-clarification choices."""
    text = str(raw_value or "").strip()
    today_value = today or date.today()
    if not text:
        return HistoryDateResolution(
            parsed_date=None,
            error_message="Не увидела дату. Введи ее в формате YYYY-MM-DD, DD.MM.YYYY, 8/6/2025 или 5 июня 2026.",
            clarification_dates=[],
        )

    clarification_dates = build_two_digit_year_clarification_dates(text, today=today_value)
    if clarification_dates:
        return HistoryDateResolution(parsed_date=None, error_message=None, clarification_dates=clarification_dates)

    parsed_date = parse_calendar_date(text)
    if parsed_date is None:
        return HistoryDateResolution(
            parsed_date=None,
            error_message="Не получилось распознать дату. Введи ее в формате YYYY-MM-DD, DD.MM.YYYY, 8/6/2025 или 5 июня 2026.",
            clarification_dates=[],
        )
    if parsed_date >= today_value:
        return HistoryDateResolution(
            parsed_date=None,
            error_message="Нужна дата из прошлого. Введи день раньше сегодняшнего, например 2026-06-05 или 05.06.2026.",
            clarification_dates=[],
        )
    return HistoryDateResolution(parsed_date=parsed_date, error_message=None, clarification_dates=[])


def build_two_digit_year_clarification_dates(raw_value: str, *, today: date | None = None) -> list[date]:
    """Builds valid day-first clarification options for dates like 8/06/25."""
    parsed = parse_day_first_short_year_date(raw_value)
    if parsed is None:
        return []

    today_value = today or date.today()
    options: list[date] = []
    for full_year in (2000 + parsed.year_two_digits, 1900 + parsed.year_two_digits):
        try:
            candidate = date(full_year, parsed.month, parsed.day)
        except ValueError:
            continue
        if candidate >= today_value:
            continue
        options.append(candidate)

    unique_options: list[date] = []
    seen: set[date] = set()
    for candidate in options:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique_options.append(candidate)
    return unique_options


def build_two_digit_year_future_warning(raw_value: str, *, today: date | None = None) -> str | None:
    """Returns an explanation when the 20YY candidate is excluded because it is a future date.

    Example: "15.07.26" → "15.07.2026 пока будущая дата, поэтому для архивной
    справки доступен только 15.07.1926."
    """
    parsed = parse_day_first_short_year_date(raw_value)
    if parsed is None:
        return None
    today_value = today or date.today()
    try:
        future_candidate = date(2000 + parsed.year_two_digits, parsed.month, parsed.day)
    except ValueError:
        return None
    if future_candidate < today_value:
        return None
    try:
        past_candidate = date(1900 + parsed.year_two_digits, parsed.month, parsed.day)
    except ValueError:
        return None
    if past_candidate >= today_value:
        return None
    return (
        f"{future_candidate.strftime('%d.%m.%Y')} пока будущая дата, "
        f"поэтому для архивной справки доступен только {past_candidate.strftime('%d.%m.%Y')}."
    )


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
