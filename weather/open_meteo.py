"""
Open-Meteo client and OpenWeather-compatible adapters (experimental).

Open-Meteo forecast data is licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). The free public API is
intended for non-commercial fair-use; see Open-Meteo documentation for
rate limits and attribution requirements.

This module exposes HTTP fetch helpers and pure mapping functions for
Open-Meteo forecast/current/geocode fallbacks behind env flags in ``weather.api``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

_CURRENT_VARS = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,"
    "pressure_msl,weather_code,wind_speed_10m,wind_direction_10m"
)
_HOURLY_VARS = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,"
    "pressure_msl,weather_code,wind_speed_10m,wind_direction_10m,"
    "precipitation_probability,precipitation"
)
_HISTORY_DAILY_VARS = (
    "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
    "precipitation_sum,rain_sum,snowfall_sum,"
    "wind_speed_10m_max,wind_direction_10m_dominant,"
    "relative_humidity_2m_mean,pressure_msl_mean,surface_pressure_mean,weather_code"
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


def _parse_om_time(
    time_str: object,
    utc_offset_seconds: int = 0,
    *,
    zone: tzinfo | None = None,
    fold: int = 0,
) -> datetime | None:
    """
    Parse an Open-Meteo time string into an aware UTC datetime.

    Open-Meteo returns naive *local wall-clock* times in the requested timezone
    (``timezone=auto`` -> the location's zone), not UTC. A naive value is interpreted in
    ``zone`` (the IANA zone from the payload) when given, so the effective UTC offset follows
    that timestamp's own DST state; ``fold`` picks the occurrence of a repeated wall-clock hour.
    Without ``zone`` the payload's fixed ``utc_offset_seconds`` is used instead.
    Values that carry an explicit offset / ``Z`` are honored as-is.
    """
    if not isinstance(time_str, str) or not time_str.strip():
        return None
    raw = time_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        if zone is not None:
            dt = dt.replace(tzinfo=zone, fold=fold)
        else:
            try:
                dt = dt.replace(tzinfo=timezone(timedelta(seconds=utc_offset_seconds)))
            except (ValueError, OverflowError):
                return None
    return dt.astimezone(timezone.utc)


def _utc_offset_seconds(om_root: dict[str, Any]) -> int:
    raw = om_root.get("utc_offset_seconds")
    if isinstance(raw, (int, float)):
        return int(raw)
    return 0


def _payload_zone(om_root: dict[str, Any]) -> ZoneInfo | None:
    """
    IANA zone Open-Meteo reported for the location (``"timezone": "Europe/Berlin"``), or None.

    None means "use the fixed ``utc_offset_seconds``": the identifier is absent, is the literal
    request value ``"auto"``, is malformed, or the local tz database does not know it.
    """
    name = om_root.get("timezone")
    if not isinstance(name, str) or not name.strip() or name.strip().lower() == "auto":
        return None
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError, OSError):
        logger.warning("Open-Meteo timezone %r is not resolvable; using fixed utc_offset_seconds", name)
        return None


def _local_offset_seconds(instant_utc: datetime, zone: ZoneInfo | None, fallback_seconds: int) -> int:
    """UTC offset in effect at ``instant_utc`` in ``zone`` (``fallback_seconds`` without a zone)."""
    if zone is None:
        return fallback_seconds
    offset = instant_utc.astimezone(zone).utcoffset()
    return int(offset.total_seconds()) if offset is not None else fallback_seconds


def _pressure_hpa(current: dict[str, Any]) -> float | None:
    p = _num(current.get("pressure_msl"))
    if p is not None:
        return p
    return _num(current.get("surface_pressure"))


def fetch_open_meteo_forecast_bundle(
    lat: float,
    lon: float,
    *,
    timezone: str = "auto",
    forecast_days: int = 5,
    timeout: int = 10,
) -> dict[str, Any] | None:
    """
    Fetch Open-Meteo /v1/forecast JSON for current + hourly variables.
    No API key. Returns parsed dict or None on transport/parse failure.

    ``timezone="auto"`` resolves the location's real timezone: the response then
    carries local wall-clock ``time`` values, the IANA ``timezone`` id (e.g. ``Europe/Berlin``)
    and ``utc_offset_seconds``, which the mappers below use to build OpenWeather-like UTC
    ``dt`` and a per-slot ``_timezone_offset``.
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


def fetch_open_meteo_geocode(
    name: str,
    *,
    count: int = 10,
    language: str = "ru",
    timeout: int = 10,
) -> dict[str, Any] | None:
    """
    GET Open-Meteo geocoding ``/v1/search``. No API key.
    Returns parsed JSON root or None on failure / empty name.
    """
    query = (name or "").strip()
    if len(query) < 2:
        return None
    params = {
        "name": query,
        "count": max(1, min(int(count), 100)),
        "language": (language or "en").lower(),
        "format": "json",
    }
    try:
        response = requests.get(OPEN_METEO_GEOCODE_URL, params=params, timeout=timeout)
    except requests.RequestException:
        logger.warning("Open-Meteo geocode request failed for name=%r", query, exc_info=True)
        return None
    if response.status_code != 200:
        logger.warning("Open-Meteo geocode HTTP %s for name=%r", response.status_code, query)
        return None
    try:
        data = response.json()
    except ValueError:
        logger.warning("Open-Meteo geocode invalid JSON for name=%r", query)
        return None
    if not isinstance(data, dict):
        return None
    return data


def fetch_open_meteo_history_daily_range(
    lat: float,
    lon: float,
    *,
    start_date: date,
    end_date: date,
    timezone: str = "auto",
    timeout: int = 10,
) -> dict[str, Any] | None:
    """
    Fetch Open-Meteo historical daily data for a calendar date range.

    The Historical Weather API uses the dedicated archive endpoint and requires
    ``timezone`` when requesting ``daily`` aggregations.
    """
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_iso,
        "end_date": end_iso,
        "daily": _HISTORY_DAILY_VARS,
        "timezone": timezone,
        "wind_speed_unit": "ms",
    }
    try:
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=timeout)
    except requests.RequestException:
        logger.warning(
            "Open-Meteo archive request failed for lat=%s lon=%s start=%s end=%s",
            lat,
            lon,
            start_iso,
            end_iso,
            exc_info=True,
        )
        return None
    if response.status_code != 200:
        logger.warning(
            "Open-Meteo archive HTTP %s for lat=%s lon=%s start=%s end=%s",
            response.status_code,
            lat,
            lon,
            start_iso,
            end_iso,
        )
        return None
    try:
        data = response.json()
    except ValueError:
        logger.warning(
            "Open-Meteo archive invalid JSON for lat=%s lon=%s start=%s end=%s",
            lat,
            lon,
            start_iso,
            end_iso,
        )
        return None
    if not isinstance(data, dict):
        return None
    return data


def fetch_open_meteo_history_daily(
    lat: float,
    lon: float,
    *,
    target_date: date,
    timezone: str = "auto",
    timeout: int = 10,
) -> dict[str, Any] | None:
    """Fetch Open-Meteo historical daily data for one calendar day."""
    return fetch_open_meteo_history_daily_range(
        lat,
        lon,
        start_date=target_date,
        end_date=target_date,
        timezone=timezone,
        timeout=timeout,
    )


def map_open_meteo_geocode_to_ow_candidates(root: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Map Open-Meteo ``/v1/search`` JSON to OpenWeather geo/1.0/direct-like dicts
    for ``_enrich_location_item`` / ``rank_locations`` / ``cleanup_location_candidates``.
    """
    if not isinstance(root, dict):
        return []
    raw_results = root.get("results")
    if not isinstance(raw_results, list) or not raw_results:
        return []
    out: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        try:
            lat_f = float(item.get("latitude"))
            lon_f = float(item.get("longitude"))
        except (TypeError, ValueError):
            continue
        cc = item.get("country_code")
        if not isinstance(cc, str) or len(cc.strip()) != 2:
            continue
        nm = item.get("name")
        if not isinstance(nm, str) or not nm.strip():
            continue
        admin1 = item.get("admin1")
        state = admin1.strip() if isinstance(admin1, str) else ""
        row: dict[str, Any] = {
            "name": nm.strip(),
            "lat": lat_f,
            "lon": lon_f,
            "country": cc.strip().upper(),
            "state": state,
            "local_names": {"ru": nm.strip()},
            "_provider": "open_meteo",
        }
        pop = item.get("population")
        if isinstance(pop, int):
            row["population"] = pop
        elif isinstance(pop, float) and pop.is_integer():
            row["population"] = int(pop)
        out.append(row)
    return out


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
    if isinstance(om.get("utc_offset_seconds"), (int, float)):
        # OpenWeather /weather-shaped shift from UTC in seconds. Prefer the offset in effect at
        # ``current.time`` (zone-aware) over the payload-wide value, which can differ across DST.
        payload_offset = _utc_offset_seconds(om)
        zone = _payload_zone(om)
        current_utc = _parse_om_time(cur.get("time"), payload_offset, zone=zone)
        out["timezone"] = (
            _local_offset_seconds(current_utc, zone, payload_offset) if current_utc is not None else payload_offset
        )
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

    Open-Meteo ``time`` values are local wall-clock times in the payload's IANA ``timezone``.
    ``dt`` / ``dt_txt`` are converted to UTC (OpenWeather convention) and the offset in effect
    *at that slot* is kept in ``_timezone_offset``, so ``dt + _timezone_offset`` is exactly the
    local time Open-Meteo reported and day grouping matches the location's calendar days, also
    when a DST transition falls inside the forecast window (offsets then differ between slots).
    If the payload has no usable IANA id, the fixed ``utc_offset_seconds`` is used for all slots.
    A wall-clock hour repeated on a fall-back day is resolved to the later instant on its
    second occurrence (the series is read in order and must stay increasing in UTC).
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
    zone = _payload_zone(om)
    step = max(1, int(every_nth_hour))

    # Resolve every hourly row (not only the sampled ones) so a repeated wall-clock hour on a
    # fall-back day is detected before downsampling.
    instants: list[datetime | None] = []
    previous_utc: datetime | None = None
    for time_str in times[:n]:
        dt = _parse_om_time(time_str, offset_sec, zone=zone)
        if dt is not None and zone is not None and previous_utc is not None and dt <= previous_utc:
            later = _parse_om_time(time_str, offset_sec, zone=zone, fold=1)
            if later is not None and later > previous_utc:
                dt = later
        if dt is not None:
            previous_utc = dt
        instants.append(dt)

    slots: list[dict[str, Any]] = []
    for i in range(0, n, step):
        dt = instants[i]
        if dt is None:
            continue
        slot_offset_sec = _local_offset_seconds(dt, zone, offset_sec)
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
                "_timezone_offset": slot_offset_sec,
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
