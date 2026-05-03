"""
Open-Meteo client and OpenWeather-compatible adapters (experimental).

Open-Meteo forecast data is licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). The free public API is
intended for non-commercial fair-use; see Open-Meteo documentation for
rate limits and attribution requirements.

This module is intentionally unwired from bot flows: it only exposes HTTP
fetch helpers and pure mapping functions for later fallback / dual-source UX.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_CURRENT_VARS = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,"
    "pressure_msl,weather_code,wind_speed_10m,wind_direction_10m"
)
_HOURLY_VARS = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,"
    "pressure_msl,weather_code,wind_speed_10m,wind_direction_10m,"
    "precipitation_probability,precipitation"
)


def weather_code_to_description_ru(code: object) -> str:
    """
    Conservative WMO weathercode (Open-Meteo) → short Russian description.
    Aligned with normalize_weather_description / alerts keyword heuristics.
    """
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "без описания"

    if c == 0:
        return "ясно"
    if c in (1, 2):
        return "переменная облачность"
    if c == 3:
        return "пасмурно"
    if c in (45, 48):
        return "туман"
    if c in (51, 53, 55):
        return "небольшой дождь"
    if c in (56, 57):
        return "дождь"
    if c in (61, 63, 65, 80, 81, 82):
        return "дождь"
    if c in (66, 67):
        return "дождь"
    if c in (71, 73, 75, 77, 85, 86):
        return "снег"
    if c in (95, 96, 99):
        return "гроза"
    return "без описания"


def _num(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _parse_om_time(time_str: object) -> datetime | None:
    if not isinstance(time_str, str) or not time_str.strip():
        return None
    raw = time_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _utc_offset_seconds(om_root: dict[str, Any]) -> int:
    raw = om_root.get("utc_offset_seconds")
    if isinstance(raw, (int, float)):
        return int(raw)
    return 0


def _pressure_hpa(current: dict[str, Any]) -> float | None:
    p = _num(current.get("pressure_msl"))
    if p is not None:
        return p
    return _num(current.get("surface_pressure"))


def fetch_open_meteo_forecast_bundle(
    lat: float,
    lon: float,
    *,
    timezone: str = "UTC",
    forecast_days: int = 5,
    timeout: int = 10,
) -> dict[str, Any] | None:
    """
    Fetch Open-Meteo /v1/forecast JSON for current + hourly variables.
    No API key. Returns parsed dict or None on transport/parse failure.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": timezone,
        "forecast_days": max(1, min(int(forecast_days), 16)),
        "wind_speed_unit": "ms",
        "current": _CURRENT_VARS,
        "hourly": _HOURLY_VARS,
    }
    try:
        response = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=timeout)
    except requests.RequestException:
        logger.warning("Open-Meteo request failed for lat=%s lon=%s", lat, lon, exc_info=True)
        return None
    if response.status_code != 200:
        logger.warning(
            "Open-Meteo HTTP %s for lat=%s lon=%s",
            response.status_code,
            lat,
            lon,
        )
        return None
    try:
        data = response.json()
    except ValueError:
        logger.warning("Open-Meteo invalid JSON for lat=%s lon=%s", lat, lon)
        return None
    if not isinstance(data, dict):
        return None
    return data


def map_open_meteo_to_current_weather(om: dict[str, Any]) -> dict[str, Any] | None:
    """
    Map Open-Meteo /v1/forecast root JSON to OpenWeather /weather-like dict
    for format_weather_response (main / weather / wind). Pressure in hPa.
    Wind speed in m/s (request wind_speed_unit=ms when fetching).
    """
    if not isinstance(om, dict):
        return None
    cur = om.get("current")
    if not isinstance(cur, dict):
        return None

    temp = _num(cur.get("temperature_2m"))
    feels = _num(cur.get("apparent_temperature"))
    humidity = _num(cur.get("relative_humidity_2m"))
    pressure = _pressure_hpa(cur)
    code = cur.get("weather_code")
    wind_speed = _num(cur.get("wind_speed_10m"))
    wind_deg = cur.get("wind_direction_10m")
    wind_deg_f: float | int | None
    if isinstance(wind_deg, (int, float)):
        wind_deg_f = int(wind_deg) if float(wind_deg).is_integer() else float(wind_deg)
    else:
        wind_deg_f = None

    weather_desc = weather_code_to_description_ru(code)

    out: dict[str, Any] = {
        "main": {
            "temp": temp,
            "feels_like": feels,
            "humidity": humidity,
            "pressure": pressure,
        },
        "weather": [{"description": weather_desc}],
        "wind": {
            "speed": wind_speed,
            "deg": wind_deg_f,
        },
    }
    return out


def _hourly_series(hourly: dict[str, Any], key: str) -> list[Any]:
    raw = hourly.get(key)
    if isinstance(raw, list):
        return raw
    return []


def map_open_meteo_to_forecast_slots(
    om: dict[str, Any],
    *,
    every_nth_hour: int = 3,
) -> list[dict[str, Any]]:
    """
    Map Open-Meteo hourly series to OpenWeather 5d/3h-like slot dicts.

    Deterministic downsampling: if Open-Meteo returns hourly rows, keep every
    ``every_nth_hour``-th row (default 3 → ~3 h cadence, similar to OW 3h slots).

    Each slot includes dt, dt_txt (UTC), _timezone_offset, main, weather, wind, pop.
    """
    if not isinstance(om, dict):
        return []
    hourly = om.get("hourly")
    if not isinstance(hourly, dict):
        return []

    times = _hourly_series(hourly, "time")
    if not times:
        return []

    keys = (
        "temperature_2m",
        "apparent_temperature",
        "relative_humidity_2m",
        "pressure_msl",
        "surface_pressure",
        "weather_code",
        "wind_speed_10m",
        "wind_direction_10m",
        "precipitation_probability",
        "precipitation",
    )
    series: dict[str, list[Any]] = {k: _hourly_series(hourly, k) for k in keys}

    n = len(times)
    for key in keys:
        seq = series.get(key, [])
        if seq:
            n = min(n, len(seq))
    offset_sec = _utc_offset_seconds(om)
    step = max(1, int(every_nth_hour))

    slots: list[dict[str, Any]] = []
    for i in range(0, n, step):
        time_str = times[i]
        dt = _parse_om_time(time_str)
        if dt is None:
            continue
        unix_utc = int(dt.timestamp())
        dt_txt = dt.strftime("%Y-%m-%d %H:%M:%S")

        def at(series_key: str) -> Any:
            seq = series.get(series_key, [])
            return seq[i] if i < len(seq) else None

        temp = _num(at("temperature_2m"))
        feels = _num(at("apparent_temperature"))
        humidity = _num(at("relative_humidity_2m"))
        pressure = _num(at("pressure_msl"))
        if pressure is None:
            pressure = _num(at("surface_pressure"))

        code = at("weather_code")
        wind_speed = _num(at("wind_speed_10m"))
        wind_dir = at("wind_direction_10m")
        wind_deg_out: float | int | None
        if isinstance(wind_dir, (int, float)):
            wind_deg_out = int(wind_dir) if float(wind_dir).is_integer() else float(wind_dir)
        else:
            wind_deg_out = None

        pop_raw = at("precipitation_probability")
        pop: float | None
        if isinstance(pop_raw, (int, float)):
            pop = max(0.0, min(1.0, float(pop_raw) / 100.0))
        else:
            pop = None

        slots.append(
            {
                "dt": unix_utc,
                "dt_txt": dt_txt,
                "_timezone_offset": offset_sec,
                "main": {
                    "temp": temp,
                    "feels_like": feels,
                    "humidity": humidity,
                    "pressure": pressure,
                },
                "weather": [{"description": weather_code_to_description_ru(code)}],
                "wind": {"speed": wind_speed, "deg": wind_deg_out},
                "pop": pop,
            }
        )
    return slots
