"""Cache/signature helpers extracted from AiWeatherService."""

import hashlib
import json


def build_cache_key(model: str, scenario: str, signature: dict) -> str:
    payload = {"scenario": scenario, "model": model, "signature": signature}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"ai:{scenario}:{digest}"


def round_1(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value), 1)
    return None


def round_step(value: object, *, step: float) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    if step <= 0:
        return float(value)
    return round(round(float(value) / step) * step, 3)


def round_coords(value: object) -> str:
    if not isinstance(value, (int, float)):
        return ""
    return f"{round(float(value), 3):.3f}"


def as_int(value: object) -> int | None:
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    return None


def normalize_location(value: object) -> str:
    text = str(value or "").strip().lower()
    return " ".join(text.split())


def normalize_description(value: object) -> str:
    text = str(value or "").strip().lower()
    return " ".join(text.split())


def normalize_query_text(value: object) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    return " ".join(text.split())


def air_quality_signature(air_quality_data: dict | None) -> dict | None:
    if not isinstance(air_quality_data, dict):
        return None
    return {
        "pm2_5": round_1(air_quality_data.get("pm2_5")),
        "pm10": round_1(air_quality_data.get("pm10")),
        "no2": round_1(air_quality_data.get("no2")),
        "o3": round_1(air_quality_data.get("o3")),
        "so2": round_1(air_quality_data.get("so2")),
        "co": round_1(air_quality_data.get("co")),
    }


def build_location_fingerprint(payload: dict) -> str:
    country = normalize_location(payload.get("country"))
    state = normalize_location(payload.get("state"))
    city = normalize_location(payload.get("city_label"))
    lat = round_coords(payload.get("lat"))
    lon = round_coords(payload.get("lon"))
    return f"{country}|{state}|{city}|{lat}|{lon}"


def first_weather_item(weather_value: object) -> dict:
    if isinstance(weather_value, list) and weather_value and isinstance(weather_value[0], dict):
        return weather_value[0]
    return {}


def current_signature(city_label: str, weather_data: dict) -> dict:
    main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
    wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
    weather_item = first_weather_item(weather_data.get("weather") if isinstance(weather_data, dict) else None)
    return {
        "location": normalize_location(city_label),
        "temp": round_step(main_data.get("temp"), step=0.5),
        "feels_like": round_step(main_data.get("feels_like"), step=0.5),
        "humidity": as_int(main_data.get("humidity")),
        "pressure": as_int(main_data.get("pressure")),
        "description": normalize_description(weather_item.get("description")),
        "wind_speed": round_step(wind_data.get("speed"), step=1.0),
    }


def forecast_signature(city_label: str, day_forecast_data: list[dict]) -> dict:
    slots: list[dict] = []
    for item in day_forecast_data if isinstance(day_forecast_data, list) else []:
        if not isinstance(item, dict):
            continue
        main_data = item.get("main", {}) if isinstance(item.get("main"), dict) else {}
        weather_item = first_weather_item(item.get("weather"))
        slots.append(
            {
                "dt_txt": item.get("dt_txt"),
                "temp": main_data.get("temp"),
                "temp_min": main_data.get("temp_min"),
                "temp_max": main_data.get("temp_max"),
                "humidity": main_data.get("humidity"),
                "description": weather_item.get("description"),
                "pop": item.get("pop"),
            }
        )
    return {"location": str(city_label).strip().lower(), "slots": slots}


def details_signature(city_label: str, weather_data: dict, air_quality_data: dict | None) -> dict:
    main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
    wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
    weather_item = first_weather_item(weather_data.get("weather") if isinstance(weather_data, dict) else None)
    return {
        "location": str(city_label).strip().lower(),
        "temp": round_1(main_data.get("temp")),
        "feels_like": round_1(main_data.get("feels_like")),
        "humidity": as_int(main_data.get("humidity")),
        "pressure": as_int(main_data.get("pressure")),
        "visibility": weather_data.get("visibility") if isinstance(weather_data, dict) else None,
        "description": weather_item.get("description"),
        "wind_speed": round_1(wind_data.get("speed")),
        "wind_deg": wind_data.get("deg"),
        "air_quality": air_quality_signature(air_quality_data),
    }


def weather_alert_signature(location_label: str, alert_payload: dict) -> dict:
    payload = alert_payload if isinstance(alert_payload, dict) else {}
    return {
        "mode": "alert",
        "format_version": "weather_alert_v1",
        "location": normalize_location(location_label),
        "event_type": normalize_location(payload.get("event_type")),
        "slot_ts_utc": as_int(payload.get("slot_ts_utc")),
        "slot_local": normalize_location(payload.get("slot_local")),
        "temperature": round_step(payload.get("temperature"), step=0.5),
        "feels_like": round_step(payload.get("feels_like"), step=0.5),
        "description": normalize_description(payload.get("description")),
        "wind_speed": round_step(payload.get("wind_speed"), step=1.0),
        "precip_probability": round_1(payload.get("precip_probability")),
    }


def location_assist_signature(user_input: str, context: dict | None) -> dict:
    ctx = context if isinstance(context, dict) else {}
    return {
        "mode": "location_assist",
        "format_version": "location_assist_v1",
        "query": normalize_query_text(user_input),
        "scenario": normalize_query_text(ctx.get("scenario")),
        "language": normalize_query_text(ctx.get("language") or "ru"),
    }


def compare_current_signature(payload_1: dict, payload_2: dict) -> dict:
    return {
        "mode": "current",
        "format_version": "deterministic_current_v1",
        "location_1": {
            "label": normalize_location(payload_1.get("city_label")),
            "fingerprint": build_location_fingerprint(payload_1),
        },
        "temp_1": round_step(payload_1.get("temperature"), step=0.5),
        "feels_1": round_step(payload_1.get("feels_like"), step=0.5),
        "desc_1": normalize_description(payload_1.get("description")),
        "humidity_1": as_int(payload_1.get("humidity")),
        "wind_1": round_step(payload_1.get("wind_speed"), step=1.0),
        "location_2": {
            "label": normalize_location(payload_2.get("city_label")),
            "fingerprint": build_location_fingerprint(payload_2),
        },
        "temp_2": round_step(payload_2.get("temperature"), step=0.5),
        "feels_2": round_step(payload_2.get("feels_like"), step=0.5),
        "desc_2": normalize_description(payload_2.get("description")),
        "humidity_2": as_int(payload_2.get("humidity")),
        "wind_2": round_step(payload_2.get("wind_speed"), step=1.0),
    }


def compare_forecast_day_signature(payload_1: dict, payload_2: dict, selected_day: str) -> dict:
    return {
        "mode": "date",
        "format_version": "deterministic_v3",
        "selected_day": normalize_location(selected_day),
        "location_1": {
            "label": normalize_location(payload_1.get("city_label")),
            "fingerprint": build_location_fingerprint(payload_1),
        },
        "min_temp_1": round_step(payload_1.get("min_temp"), step=0.5),
        "max_temp_1": round_step(payload_1.get("max_temp"), step=0.5),
        "dominant_desc_1": normalize_description(payload_1.get("dominant_description")),
        "rain_slots_1": as_int((payload_1.get("precipitation_signal") or {}).get("rain_slots")),
        "max_pop_1": round_1((payload_1.get("precipitation_signal") or {}).get("max_pop")),
        "location_2": {
            "label": normalize_location(payload_2.get("city_label")),
            "fingerprint": build_location_fingerprint(payload_2),
        },
        "min_temp_2": round_step(payload_2.get("min_temp"), step=0.5),
        "max_temp_2": round_step(payload_2.get("max_temp"), step=0.5),
        "dominant_desc_2": normalize_description(payload_2.get("dominant_description")),
        "rain_slots_2": as_int((payload_2.get("precipitation_signal") or {}).get("rain_slots")),
        "max_pop_2": round_1((payload_2.get("precipitation_signal") or {}).get("max_pop")),
    }

