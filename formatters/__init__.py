"""
Backward-compatible re-exports for the formatters package.

All public names that were previously available from the flat `formatters`
module remain importable from `formatters` without any changes to call sites.

Internal package structure:
  formatters.common        — shared helpers (wind_direction_ru, _wind_text_from_values)
  formatters.weather       — current weather, details, alerts, locations, help
  formatters.forecast      — today/tomorrow/5-day forecast, two-city compare
  formatters.history       — daily history, monthly climate normals
  formatters.source_compare — OpenWeather vs Open-Meteo deterministic comparison
"""

from formatters.weather import (
    help_text,
    format_saved_locations,
    format_alerts_status,
    format_alert_subscriptions,
    format_weather_response,
    format_details_response,
)

from formatters.forecast import (
    format_tomorrow_forecast_response,
    format_today_forecast_response,
    format_compare_response,
)

from formatters.history import (
    build_history_brief_summary,
    format_history_weather_response,
    build_monthly_climate_brief_summary,
    format_history_monthly_climate_response,
)

from formatters.source_compare import (
    format_source_compare_response,
    format_source_compare_current_response,
)

# Also re-export wind_direction_ru from common — it was public in the original module.
from formatters.common import wind_direction_ru

__all__ = [
    # weather
    "help_text",
    "format_saved_locations",
    "format_alerts_status",
    "format_alert_subscriptions",
    "format_weather_response",
    "format_details_response",
    # forecast
    "format_tomorrow_forecast_response",
    "format_today_forecast_response",
    "format_compare_response",
    # history
    "build_history_brief_summary",
    "format_history_weather_response",
    "build_monthly_climate_brief_summary",
    "format_history_monthly_climate_response",
    # source compare
    "format_source_compare_response",
    "format_source_compare_current_response",
    # shared
    "wind_direction_ru",
]
