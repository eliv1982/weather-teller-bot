"""Пакет погодных модулей: API, локации и качество воздуха."""

from .api import (
    LAST_ERROR_TYPE,
    OW_API_KEY,
    get_air_pollution,
    get_coordinates,
    get_current_weather,
    get_forecast_5d3h,
    get_location_by_coordinates,
    get_locations,
    safe_request,
)
from .air_quality import analyze_air_pollution
from .locations import (
    build_disambiguated_location_labels,
    build_geocode_item_with_disambiguated_label,
    build_location_label,
    contains_cyrillic,
    get_city_name_ru,
    get_country_name_ru,
    get_region_name_ru,
    location_label_plain,
    location_label_with_coords,
    rank_locations,
)

__all__ = [
    "OW_API_KEY",
    "LAST_ERROR_TYPE",
    "safe_request",
    "contains_cyrillic",
    "get_country_name_ru",
    "get_city_name_ru",
    "get_region_name_ru",
    "build_location_label",
    "location_label_plain",
    "location_label_with_coords",
    "build_disambiguated_location_labels",
    "build_geocode_item_with_disambiguated_label",
    "rank_locations",
    "get_locations",
    "get_location_by_coordinates",
    "get_current_weather",
    "get_coordinates",
    "get_forecast_5d3h",
    "get_air_pollution",
    "analyze_air_pollution",
]
