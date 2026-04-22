from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AppContext:
    """Контейнер общих зависимостей приложения."""

    bot: Any
    logger: Any
    load_user: Any
    save_user: Any
    load_all_users: Any
    save_all_users: Any
    main_menu: Any
    alerts_menu: Any
    alerts_add_location_menu: Any
    locations_menu: Any
    add_saved_location_menu: Any
    geo_request_menu: Any
    build_current_weather_location_keyboard: Any
    build_forecast_days_keyboard: Any
    build_forecast_day_keyboard: Any
    build_location_pick_keyboard: Any
    build_alert_subscriptions_keyboard: Any
    build_saved_locations_keyboard: Any
    build_scenario_location_choice_keyboard: Any
    build_favorite_pick_keyboard: Any
    format_alerts_status: Any
    format_alert_subscriptions: Any
    format_compare_response: Any
    format_details_response: Any
    format_saved_locations: Any
    format_weather_response: Any
    help_text: Any
    ensure_notifications_defaults: Any
    ensure_alert_subscriptions_defaults: Any
    migrate_legacy_alert_to_subscriptions: Any
    add_alert_subscription: Any
    detect_weather_alerts: Any
    save_saved_location_item: Any
    complete_current_weather_from_location: Any
    complete_alerts_location_from_item: Any
    group_forecast_by_day: Any
    format_forecast_day: Any
    build_geocode_item_with_disambiguated_label: Any
    rank_locations: Any
    get_locations: Any
    build_location_label: Any
    get_location_by_coordinates: Any
    get_current_weather: Any
    get_forecast_5d3h: Any
    get_air_pollution: Any
