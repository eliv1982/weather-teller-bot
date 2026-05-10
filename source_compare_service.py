from __future__ import annotations

from typing import Any

from forecast_service import get_today_forecast_day, get_tomorrow_forecast_day, group_forecast_by_day, is_remaining_day_forecast
from handlers.location_compare_helpers import _ai_compare_day_payload, _format_precipitation_summary
from weather.api import (
    get_current_weather_open_meteo_direct,
    get_current_weather_openweather_only,
    get_forecast_5d3h_open_meteo_direct,
    get_forecast_5d3h_openweather_only,
)


def _summarize_current_wind_direction(wind_deg: object) -> str | None:
    if not isinstance(wind_deg, (int, float)):
        return None
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
    index = round(float(wind_deg) / 45) % 8
    return directions[index]


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
    payload["source_slot_count"] = len(day_items)
    return payload


def build_provider_current_summary(city_label: str, provider_name: str, weather: dict[str, Any]) -> dict[str, Any]:
    main = weather.get("main") if isinstance(weather, dict) else {}
    wind = weather.get("wind") if isinstance(weather, dict) else {}
    weather_list = weather.get("weather") if isinstance(weather, dict) else []
    weather_item = weather_list[0] if isinstance(weather_list, list) and weather_list and isinstance(weather_list[0], dict) else {}

    temp = main.get("temp") if isinstance(main, dict) else None
    feels_like = main.get("feels_like") if isinstance(main, dict) else None
    humidity = main.get("humidity") if isinstance(main, dict) else None
    pressure = main.get("pressure") if isinstance(main, dict) else None
    wind_speed = wind.get("speed") if isinstance(wind, dict) else None
    wind_deg = wind.get("deg") if isinstance(wind, dict) else None
    description = str(weather_item.get("description") or "без описания")
    desc_lower = description.lower()
    if any(marker in desc_lower for marker in ("дожд", "лив", "гроза", "снег")):
        precipitation_text = "осадки есть"
    else:
        precipitation_text = "без осадков"

    payload: dict[str, Any] = {
        "provider_name": provider_name,
        "city_label": city_label,
        "temperature": temp,
        "feels_like": feels_like,
        "humidity": humidity,
        "pressure": pressure,
        "dominant_description": description,
        "precipitation_text": precipitation_text,
        "wind_text": _wind_label({"wind_signal": {"max_speed": wind_speed}}),
        "wind_signal": {
            "min_speed": wind_speed,
            "avg_speed": wind_speed,
            "max_speed": wind_speed,
        },
        "wind_direction_text": _summarize_current_wind_direction(wind_deg),
        "min_temp": temp,
        "max_temp": temp,
    }
    if isinstance(feels_like, (int, float)):
        payload["min_feels_like"] = feels_like
        payload["max_feels_like"] = feels_like
    if isinstance(humidity, (int, float)):
        payload["min_humidity"] = humidity
        payload["max_humidity"] = humidity
    if isinstance(pressure, (int, float)):
        payload["min_pressure"] = pressure
        payload["max_pressure"] = pressure
    return payload


def _provider_unavailable_result(city_label: str, *, openweather_ok: bool, open_meteo_ok: bool) -> dict[str, Any]:
    if not openweather_ok and not open_meteo_ok:
        error_message = "Не удалось сравнить источники: оба прогноза сейчас недоступны."
    elif not openweather_ok:
        error_message = "Не удалось сравнить оба источника: OpenWeather сейчас не ответил, Open-Meteo ответил успешно."
    else:
        error_message = "Не удалось сравнить оба источника: Open-Meteo сейчас не ответил, OpenWeather ответил успешно."
    return {
        "ok": False,
        "error_code": "provider_unavailable",
        "error_message": error_message,
        "city_label": city_label,
        "openweather": None,
        "open_meteo": None,
    }


def _load_grouped_source_forecasts(lat: float, lon: float, city_label: str) -> dict[str, Any]:
    ow_slots = get_forecast_5d3h_openweather_only(lat, lon)
    om_slots = get_forecast_5d3h_open_meteo_direct(lat, lon)
    if not ow_slots or not om_slots:
        return _provider_unavailable_result(
            city_label,
            openweather_ok=bool(ow_slots),
            open_meteo_ok=bool(om_slots),
        )

    ow_grouped = group_forecast_by_day(ow_slots)
    om_grouped = group_forecast_by_day(om_slots)
    available_days = [day for day in ow_grouped.keys() if day in om_grouped]
    return {
        "ok": True,
        "error_code": None,
        "error_message": None,
        "city_label": city_label,
        "openweather_grouped": ow_grouped,
        "open_meteo_grouped": om_grouped,
        "available_days": available_days,
    }


def _build_day_compare_result(
    city_label: str,
    title: str,
    selected_day: str,
    openweather_day: tuple[str, list[dict]],
    open_meteo_day: tuple[str, list[dict]],
    *,
    is_remaining_day: bool = False,
) -> dict[str, Any]:
    ow_day_key, ow_items = openweather_day
    om_day_key, om_items = open_meteo_day
    return {
        "ok": True,
        "error_code": None,
        "error_message": None,
        "city_label": city_label,
        "selected_day": selected_day,
        "title": title,
        "is_remaining_day": is_remaining_day,
        "openweather": build_provider_day_summary(city_label, "OpenWeather", ow_day_key, ow_items),
        "open_meteo": build_provider_day_summary(city_label, "Open-Meteo", om_day_key, om_items),
    }


def compare_current_sources(lat: float, lon: float, city_label: str) -> dict[str, Any]:
    ow_current = get_current_weather_openweather_only(lat, lon)
    om_current = get_current_weather_open_meteo_direct(lat, lon)
    if not ow_current or not om_current:
        return _provider_unavailable_result(
            city_label,
            openweather_ok=bool(ow_current),
            open_meteo_ok=bool(om_current),
        )
    return {
        "ok": True,
        "error_code": None,
        "error_message": None,
        "city_label": city_label,
        "title": "🔎 Сравнение погоды сейчас",
        "openweather": build_provider_current_summary(city_label, "OpenWeather", ow_current),
        "open_meteo": build_provider_current_summary(city_label, "Open-Meteo", om_current),
    }


def compare_today_sources(lat: float, lon: float, city_label: str) -> dict[str, Any]:
    grouped_result = _load_grouped_source_forecasts(lat, lon, city_label)
    if not grouped_result.get("ok"):
        return grouped_result

    ow_today = get_today_forecast_day(grouped_result["openweather_grouped"])
    om_today = get_today_forecast_day(grouped_result["open_meteo_grouped"])
    if ow_today is None or om_today is None:
        return {
            "ok": False,
            "error_code": "today_missing",
            "error_message": "Не удалось найти прогноз на сегодня по одному из источников.",
            "city_label": city_label,
            "openweather": None,
            "open_meteo": None,
        }

    selected_day = ow_today[0]
    remaining_day = is_remaining_day_forecast(ow_today[1]) or is_remaining_day_forecast(om_today[1])
    title = "🔎 Сравнение прогнозов на оставшуюся часть дня" if remaining_day else "🔎 Сравнение прогнозов на сегодня"
    return _build_day_compare_result(
        city_label,
        title,
        selected_day,
        ow_today,
        om_today,
        is_remaining_day=remaining_day,
    )


def get_source_compare_available_dates(lat: float, lon: float, city_label: str) -> dict[str, Any]:
    grouped_result = _load_grouped_source_forecasts(lat, lon, city_label)
    if not grouped_result.get("ok"):
        return grouped_result
    available_days = grouped_result.get("available_days") or []
    if not available_days:
        return {
            "ok": False,
            "error_code": "dates_missing",
            "error_message": "Не удалось найти общие даты прогноза по двум источникам.",
            "city_label": city_label,
            "openweather": None,
            "open_meteo": None,
        }
    return grouped_result


def compare_tomorrow_sources(lat: float, lon: float, city_label: str) -> dict[str, Any]:
    grouped_result = _load_grouped_source_forecasts(lat, lon, city_label)
    if not grouped_result.get("ok"):
        return grouped_result

    ow_grouped = grouped_result["openweather_grouped"]
    om_grouped = grouped_result["open_meteo_grouped"]
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

    return _build_day_compare_result(
        city_label,
        "🔎 Сравнение прогнозов на завтра",
        ow_tomorrow[0],
        ow_tomorrow,
        om_tomorrow,
    )


def compare_sources_by_date(lat: float, lon: float, city_label: str, selected_day: str) -> dict[str, Any]:
    grouped_result = _load_grouped_source_forecasts(lat, lon, city_label)
    if not grouped_result.get("ok"):
        return grouped_result
    ow_grouped = grouped_result["openweather_grouped"]
    om_grouped = grouped_result["open_meteo_grouped"]
    if selected_day not in ow_grouped or selected_day not in om_grouped:
        return {
            "ok": False,
            "error_code": "date_missing",
            "error_message": "Не удалось найти выбранную дату по одному из источников.",
            "city_label": city_label,
            "openweather": None,
            "open_meteo": None,
        }
    return _build_day_compare_result(
        city_label,
        f"🔎 Сравнение прогнозов на {selected_day}",
        selected_day,
        (selected_day, ow_grouped[selected_day]),
        (selected_day, om_grouped[selected_day]),
    )
