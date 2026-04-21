import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()
OW_API_KEY = os.getenv("OW_API_KEY")

LAST_ERROR_TYPE = None  # None | "network" | "rate_limit"

COUNTRY_NAMES_RU = {
    "RU": "Россия",
    "UA": "Украина",
    "BY": "Беларусь",
    "KZ": "Казахстан",
    "US": "США",
    "GB": "Великобритания",
    "DE": "Германия",
    "FR": "Франция",
    "IT": "Италия",
    "ES": "Испания",
    "FI": "Финляндия",
    "SE": "Швеция",
    "NO": "Норвегия",
    "PL": "Польша",
    "CN": "Китай",
    "JP": "Япония",
    "TR": "Турция",
}

REGION_NAMES_RU = {
    "Saint Petersburg": "Санкт-Петербург",
    "Leningrad oblast": "Ленинградская область",
    "Kaliningrad": "Калининградская область",
    "Kaliningrad Oblast": "Калининградская область",
    "Krasnoyarsk Krai": "Красноярский край",
    "Dagestan": "Дагестан",
    "Zaporizhzhia Oblast": "Запорожская область",
    "Moscow": "Москва",
    "Moscow Oblast": "Московская область",
    "Novosibirsk Oblast": "Новосибирская область",
    "Sverdlovsk Oblast": "Свердловская область",
    "Tatarstan": "Татарстан",
}


def contains_cyrillic(text: str) -> bool:
    return any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in text)


def safe_request(
    url: str,
    params: dict,
    retries: int = 3,
    timeout: int = 10
) -> requests.Response | None:
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


def get_country_name_ru(country_code: str | None) -> str | None:
    if not country_code:
        return None
    return COUNTRY_NAMES_RU.get(country_code, country_code)


def get_city_name_ru(location: dict) -> str:
    local_names = location.get("local_names", {})
    raw_name = location.get("name", "")

    return (
        local_names.get("ru")
        or (raw_name if contains_cyrillic(raw_name) else None)
        or local_names.get("en")
        or raw_name
        or "неизвестный город"
    )


def get_region_name_ru(state: str | None) -> str | None:
    if not state:
        return None

    if state in REGION_NAMES_RU:
        return REGION_NAMES_RU[state]

    if contains_cyrillic(state):
        return state

    return None


def build_location_label(location: dict, show_coords: bool = False) -> str:
    city_name = get_city_name_ru(location)
    region_name = get_region_name_ru(location.get("state"))
    country_name = get_country_name_ru(location.get("country"))

    details = []

    if country_name:
        details.append(country_name)

    if region_name and region_name != city_name:
        details.append(region_name)

    label = city_name
    if details:
        label += f" ({', '.join(details)})"

    if show_coords:
        lat = location.get("lat")
        lon = location.get("lon")
        if lat is not None and lon is not None:
            label += f" — {lat:.4f}, {lon:.4f}"

    return label


def get_locations(city: str, limit: int = 5) -> list[dict] | None:
    if not OW_API_KEY:
        return None

    url = "https://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": city,
        "limit": limit,
        "appid": OW_API_KEY
    }

    response = safe_request(url, params)

    if response is None or response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    if not data:
        return None

    return data


def get_location_by_coordinates(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None

    url = "https://api.openweathermap.org/geo/1.0/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "limit": 1,
        "appid": OW_API_KEY
    }

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
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OW_API_KEY,
        "units": "metric",
        "lang": "ru"
    }

    response = safe_request(url, params)

    if response is None or response.status_code != 200:
        return None

    try:
        return response.json()
    except ValueError:
        return None


def get_coordinates(city: str, limit: int = 1) -> tuple[float, float] | None:
    locations = get_locations(city=city, limit=limit)
    if not locations:
        return None

    first = locations[0]
    lat = first.get("lat")
    lon = first.get("lon")

    if lat is None or lon is None:
        return None

    return lat, lon


def format_weather(weather: dict) -> str:
    location_name = (
        weather.get("_display_location")
        or weather.get("name")
        or "неизвестный город"
    )

    temp = weather.get("main", {}).get("temp")
    description = weather.get("weather", [{}])[0].get("description", "без описания")

    if temp is None:
        return f"Погода в городе {location_name}: данные о температуре недоступны."

    return f"Погода в городе {location_name}: {temp:.1f}°C, {description}"


def get_forecast_5d3h(lat: float, lon: float) -> list[dict] | None:
    if not OW_API_KEY:
        return None

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OW_API_KEY,
        "units": "metric",
        "lang": "ru",
    }
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
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OW_API_KEY,
    }
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


def analyze_air_pollution(components: dict, extended: bool = False) -> dict:
    """
    Анализирует загрязнение воздуха и возвращает итоговый статус и детали.
    Все статусы и описания возвращаются на русском языке.
    """
    if not isinstance(components, dict) or not components:
        return {
            "overall_status": "Нет данных",
            "details": "Данные о загрязнении воздуха недоступны.",
        }

    thresholds = {
        "pm2_5": {"good": 12, "moderate": 35, "bad": 55, "name": "PM2.5"},
        "pm10": {"good": 20, "moderate": 50, "bad": 100, "name": "PM10"},
        "no2": {"good": 40, "moderate": 100, "bad": 200, "name": "NO2"},
        "so2": {"good": 20, "moderate": 80, "bad": 250, "name": "SO2"},
        "o3": {"good": 60, "moderate": 120, "bad": 180, "name": "O3"},
        "co": {"good": 4400, "moderate": 9400, "bad": 12400, "name": "CO"},
    }

    severity_score = 0
    short_details = []
    detailed_details: dict[str, dict[str, Any]] = {}

    for key, rule in thresholds.items():
        value = components.get(key)
        if value is None:
            continue

        if value <= rule["good"]:
            status = "Хорошо"
            level = 0
        elif value <= rule["moderate"]:
            status = "Умеренно"
            level = 1
        elif value <= rule["bad"]:
            status = "Повышено"
            level = 2
        else:
            status = "Опасно"
            level = 3

        severity_score = max(severity_score, level)
        short_details.append(f'{rule["name"]}: {status.lower()}')
        detailed_details[key] = {
            "name": rule["name"],
            "value": value,
            "status": status,
        }

    overall_map = {
        0: "Хорошее",
        1: "Умеренное",
        2: "Повышенное",
        3: "Опасное",
    }
    overall_status = overall_map.get(severity_score, "Нет данных")

    if not extended:
        return {
            "overall_status": overall_status,
            "details": ", ".join(short_details) if short_details else "Недостаточно данных для анализа.",
        }

    return {
        "overall_status": overall_status,
        "details": detailed_details if detailed_details else "Недостаточно данных для анализа.",
    }