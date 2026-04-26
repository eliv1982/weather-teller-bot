import logging
import os
import time
import copy

import requests
from dotenv import load_dotenv

from .locations import _dedupe_geocode_sorted, _enrich_location_item, _location_relevance_score, contains_cyrillic

load_dotenv()
OW_API_KEY = os.getenv("OW_API_KEY")
LAST_ERROR_TYPE = None  # None | "network" | "rate_limit"

logger = logging.getLogger(__name__)


class TTLCache:
    """Простой in-memory TTL cache для внешних API-запросов."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        now = time.time()
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= now:
            self._store.pop(key, None)
            return None
        return copy.deepcopy(value)

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        expires_at = time.time() + float(ttl_seconds)
        self._store[key] = (expires_at, copy.deepcopy(value))

    def cleanup_expired(self) -> None:
        now = time.time()
        expired = [k for k, (exp, _) in self._store.items() if exp <= now]
        for key in expired:
            self._store.pop(key, None)


API_CACHE = TTLCache()

TTL_CURRENT_SECONDS = 2 * 60
TTL_FORECAST_SECONDS = 15 * 60
TTL_AIR_SECONDS = 15 * 60
TTL_GEOCODE_SECONDS = 30 * 60
TTL_REVERSE_GEOCODE_SECONDS = 30 * 60
def _normalize_query_for_key(query: str) -> str:
    return " ".join(str(query or "").strip().lower().split())


def _round_coord(value: float) -> float:
    return round(float(value), 4)


def _coord_cache_key(namespace: str, lat: float, lon: float) -> str:
    return f"{namespace}:{_round_coord(lat):.4f}:{_round_coord(lon):.4f}"


def _query_cache_key(namespace: str, query: str, *, limit: int) -> str:
    return f"{namespace}:{_normalize_query_for_key(query)}:limit={int(limit)}"


def _log_cache_hit(scope: str, key: str, *, query: str | None = None) -> None:
    if query is not None:
        logger.info("API cache HIT: %s query=%s key=%s", scope, query, key)
        return
    logger.info("API cache HIT: %s key=%s", scope, key)


def _log_cache_miss(scope: str, key: str, *, query: str | None = None) -> None:
    if query is not None:
        logger.info("API cache MISS: %s query=%s key=%s", scope, query, key)
        return
    logger.info("API cache MISS: %s key=%s", scope, key)


def _log_cache_set(scope: str, key: str, ttl_seconds: int, *, query: str | None = None) -> None:
    if query is not None:
        logger.info("API cache SET: %s ttl=%s query=%s key=%s", scope, ttl_seconds, query, key)
        return
    logger.info("API cache SET: %s ttl=%s key=%s", scope, ttl_seconds, key)


def safe_request(
    url: str,
    params: dict,
    retries: int = 3,
    timeout: int = 10,
) -> requests.Response | None:
    """
    Делает HTTP GET с мягким ретраем и не бросает исключения наружу.
    Возвращает requests.Response или None.
    """
    global LAST_ERROR_TYPE
    LAST_ERROR_TYPE = None
    delay = 1

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            LAST_ERROR_TYPE = "network"
            logging.exception("safe_request request exception: %s", url)
            return None

        if response.status_code == 429:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            LAST_ERROR_TYPE = "rate_limit"
            return response

        return response

    return None


def _geocode_direct_raw(q: str, limit: int = 5) -> list[dict]:
    """
    Один запрос к geo/1.0/direct без обогащения полями бота.
    У API лимит не более 5 результатов за вызов.
    """
    if not OW_API_KEY:
        return []
    query = (q or "").strip()
    if not query:
        return []
    limit = min(max(1, limit), 5)
    url = "https://api.openweathermap.org/geo/1.0/direct"
    params = {"q": query, "limit": limit, "appid": OW_API_KEY}
    response = safe_request(url, params)
    if response is None or response.status_code != 200:
        return []
    try:
        data = response.json()
    except ValueError:
        return []
    if not isinstance(data, list) or not data:
        return []
    return data


def _geocode_query_variants(query: str) -> list[str]:
    """
    Варианты строки запроса для геокодинга.
    Для кириллицы без явной страны добавляется «запрос,RU», чтобы поднять релевантные
    российские совпадения.
    """
    q = query.strip()
    if not q:
        return []
    variants = [q]
    if contains_cyrillic(q) and "," not in q:
        variants.append(f"{q},RU")
    return variants


def _collect_geocode_candidates(query: str) -> list[dict]:
    """Собирает сырые ответы API по всем вариантам запроса (без повторной обработки)."""
    merged: list[dict] = []
    for variant in _geocode_query_variants(query):
        merged.extend(_geocode_direct_raw(variant, 5))
    return merged


def get_locations(query: str, limit: int = 5) -> list[dict] | None:
    """
    Ищет населённые пункты и локации по строке запроса (OpenWeather Geocoding API).
    Возвращает список словарей с полями ответа API плюс local_name и label.
    """
    if not OW_API_KEY:
        return None
    q = (query or "").strip()
    if not q:
        return None
    cap = min(max(1, limit), 5)
    cache_key = _query_cache_key("geocode", q, limit=cap)
    cached = API_CACHE.get(cache_key)
    if cached is not None:
        _log_cache_hit("geocode", cache_key, query=_normalize_query_for_key(q))
        return cached  # type: ignore[return-value]
    _log_cache_miss("geocode", cache_key, query=_normalize_query_for_key(q))
    candidates = _collect_geocode_candidates(q)
    if not candidates:
        return None
    candidates.sort(
        key=lambda loc: (
            -_location_relevance_score(loc, q),
            0 if (loc.get("country") or "").upper() == "RU" else 1,
            (loc.get("name") or ""),
        )
    )
    deduped = _dedupe_geocode_sorted(candidates)
    final = deduped[:cap]
    result = [_enrich_location_item(item) for item in final]
    API_CACHE.set(cache_key, result, ttl_seconds=TTL_GEOCODE_SECONDS)
    _log_cache_set("geocode", cache_key, TTL_GEOCODE_SECONDS, query=_normalize_query_for_key(q))
    return result


def get_location_by_coordinates(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None
    cache_key = _coord_cache_key("reverse_geocode", lat, lon)
    cached = API_CACHE.get(cache_key)
    if cached is not None:
        _log_cache_hit("reverse_geocode", cache_key)
        return cached  # type: ignore[return-value]
    _log_cache_miss("reverse_geocode", cache_key)
    url = "https://api.openweathermap.org/geo/1.0/reverse"
    params = {"lat": lat, "lon": lon, "limit": 1, "appid": OW_API_KEY}
    response = safe_request(url, params)
    if response is None or response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    if not data:
        return None
    result = data[0]
    API_CACHE.set(cache_key, result, ttl_seconds=TTL_REVERSE_GEOCODE_SECONDS)
    _log_cache_set("reverse_geocode", cache_key, TTL_REVERSE_GEOCODE_SECONDS)
    return result


def get_current_weather(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None
    cache_key = _coord_cache_key("current", lat, lon)
    cached = API_CACHE.get(cache_key)
    if cached is not None:
        _log_cache_hit("current_weather", cache_key)
        return cached  # type: ignore[return-value]
    _log_cache_miss("current_weather", cache_key)
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lon, "appid": OW_API_KEY, "units": "metric", "lang": "ru"}
    response = safe_request(url, params)
    if response is None or response.status_code != 200:
        return None
    try:
        result = response.json()
    except ValueError:
        return None
    API_CACHE.set(cache_key, result, ttl_seconds=TTL_CURRENT_SECONDS)
    _log_cache_set("current_weather", cache_key, TTL_CURRENT_SECONDS)
    return result


def get_coordinates(query: str, limit: int = 1) -> tuple[float, float] | None:
    """
    Возвращает координаты (широта, долгота) первой найденной локации по запросу.
    Внутри используется get_locations: берётся первый вариант из списка.
    """
    locations = get_locations(query=query, limit=limit)
    if not locations:
        return None
    first = locations[0]
    lat = first.get("lat")
    lon = first.get("lon")
    if lat is None or lon is None:
        return None
    return lat, lon


def get_forecast_5d3h(lat: float, lon: float) -> list[dict] | None:
    if not OW_API_KEY:
        return None
    cache_key = _coord_cache_key("forecast", lat, lon)
    cached = API_CACHE.get(cache_key)
    if cached is not None:
        _log_cache_hit("forecast_5d3h", cache_key)
        return cached  # type: ignore[return-value]
    _log_cache_miss("forecast_5d3h", cache_key)
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": OW_API_KEY, "units": "metric", "lang": "ru"}
    response = safe_request(url, params)
    if response is None or response.status_code != 200:
        return None
    try:
        data = response.json()
        items = data.get("list")
        city = data.get("city") if isinstance(data, dict) else {}
        tz_offset = city.get("timezone", 0) if isinstance(city, dict) else 0
    except ValueError:
        return None
    if not isinstance(items, list):
        return None
    enriched: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["_timezone_offset"] = int(tz_offset) if isinstance(tz_offset, (int, float)) else 0
        enriched.append(row)
    API_CACHE.set(cache_key, enriched, ttl_seconds=TTL_FORECAST_SECONDS)
    _log_cache_set("forecast_5d3h", cache_key, TTL_FORECAST_SECONDS)
    return enriched


def get_air_pollution(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None
    cache_key = _coord_cache_key("air", lat, lon)
    cached = API_CACHE.get(cache_key)
    if cached is not None:
        _log_cache_hit("air_pollution", cache_key)
        return cached  # type: ignore[return-value]
    _log_cache_miss("air_pollution", cache_key)
    url = "https://api.openweathermap.org/data/2.5/air_pollution"
    params = {"lat": lat, "lon": lon, "appid": OW_API_KEY}
    response = safe_request(url, params)
    if response is None or response.status_code != 200:
        return None
    try:
        data = response.json()
        items = data.get("list")
        if not items:
            return None
        components = items[0].get("components")
    except (ValueError, IndexError, AttributeError):
        return None
    if not isinstance(components, dict):
        return None
    API_CACHE.set(cache_key, components, ttl_seconds=TTL_AIR_SECONDS)
    _log_cache_set("air_pollution", cache_key, TTL_AIR_SECONDS)
    return components
