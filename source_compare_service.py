from __future__ import annotations

from typing import Any

from forecast_service import get_tomorrow_forecast_day, group_forecast_by_day
from handlers.location_compare_helpers import _ai_compare_day_payload, _format_precipitation_summary
from weather.api import get_forecast_5d3h_open_meteo_direct, get_forecast_5d3h_openweather_only


def _wind_label(payload: dict[str, Any]) -> str:
    signal = payload.get("wind_signal") if isinstance(payload, dict) else {}
    max_speed = signal.get("max_speed") if isinstance(signal, dict) else None
    if not isinstance(max_speed, (int, float)):
        return "н/д"
    speed = float(max_speed)
    if speed < 4:
        return "слабый"
    if speed < 8:
        return "умеренный"
    if speed < 13:
        return "сильный"
    return "очень сильный"


def build_provider_day_summary(city_label: str, provider_name: str, day_key: str, day_items: list[dict]) -> dict[str, Any]:
    payload = _ai_compare_day_payload(city_label, day_key, day_items)
    payload["provider_name"] = provider_name
    payload["precipitation_text"] = _format_precipitation_summary(payload)
    payload["wind_text"] = _wind_label(payload)
    return payload


def compare_tomorrow_sources(lat: float, lon: float, city_label: str) -> dict[str, Any]:
    ow_slots = get_forecast_5d3h_openweather_only(lat, lon)
    om_slots = get_forecast_5d3h_open_meteo_direct(lat, lon)

    if not ow_slots or not om_slots:
        missing: list[str] = []
        if not ow_slots:
            missing.append("OpenWeather")
        if not om_slots:
            missing.append("Open-Meteo")
        if len(missing) == 2:
            error_message = "Не удалось сверить источники: оба прогноза сейчас недоступны."
        elif missing[0] == "OpenWeather":
            error_message = "Не удалось сверить оба источника: OpenWeather недоступен, Open-Meteo ответил успешно."
        else:
            error_message = "Не удалось сверить оба источника: Open-Meteo недоступен, OpenWeather ответил успешно."
        return {
            "ok": False,
            "error_code": "provider_unavailable",
            "error_message": error_message,
            "city_label": city_label,
            "openweather": None,
            "open_meteo": None,
        }

    ow_grouped = group_forecast_by_day(ow_slots)
    om_grouped = group_forecast_by_day(om_slots)
    ow_tomorrow = get_tomorrow_forecast_day(ow_grouped)
    om_tomorrow = get_tomorrow_forecast_day(om_grouped)

    if ow_tomorrow is None or om_tomorrow is None:
        return {
            "ok": False,
            "error_code": "tomorrow_missing",
            "error_message": "Не удалось найти прогноз на завтра по одному из источников.",
            "city_label": city_label,
            "openweather": None,
            "open_meteo": None,
        }

    ow_day_key, ow_items = ow_tomorrow
    om_day_key, om_items = om_tomorrow
    return {
        "ok": True,
        "error_code": None,
        "error_message": None,
        "city_label": city_label,
        "selected_day": ow_day_key,
        "openweather": build_provider_day_summary(city_label, "OpenWeather", ow_day_key, ow_items),
        "open_meteo": build_provider_day_summary(city_label, "Open-Meteo", om_day_key, om_items),
    }
