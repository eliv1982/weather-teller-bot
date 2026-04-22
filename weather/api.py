import logging
import os
import time

import requests
from dotenv import load_dotenv

from .locations import _dedupe_geocode_sorted, _enrich_location_item, _location_relevance_score, contains_cyrillic

load_dotenv()
OW_API_KEY = os.getenv("OW_API_KEY")
LAST_ERROR_TYPE = None  # None | "network" | "rate_limit"


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
    cap = min(max(1, limit), 5)
    final = deduped[:cap]
    return [_enrich_location_item(item) for item in final]


def get_location_by_coordinates(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None
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
    return data[0]


def get_current_weather(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lon, "appid": OW_API_KEY, "units": "metric", "lang": "ru"}
    response = safe_request(url, params)
    if response is None or response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


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
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": OW_API_KEY, "units": "metric", "lang": "ru"}
    response = safe_request(url, params)
    if response is None or response.status_code != 200:
        return None
    try:
        data = response.json()
        items = data.get("list")
    except ValueError:
        return None
    if not isinstance(items, list):
        return None
    return items


def get_air_pollution(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None
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
    return components
