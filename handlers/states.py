# Состояния сценария текущей погоды
WAITING_CURRENT_WEATHER_CITY = "waiting_current_weather_city"
WAITING_CURRENT_WEATHER_PICK = "waiting_current_weather_pick"

# Состояния сценария геолокации
WAITING_GEO_LOCATION = "waiting_geo_location"

# Состояния сценария расширенных данных
WAITING_DETAILS_CITY = "waiting_details_city"
WAITING_DETAILS_PICK = "waiting_details_pick"
WAITING_DETAILS_USE_SAVED_LOCATION = "waiting_details_use_saved_location"

# Состояния сценария прогноза
WAITING_FORECAST_CITY = "waiting_forecast_city"
WAITING_FORECAST_PICK = "waiting_forecast_pick"
WAITING_FORECAST_USE_SAVED_LOCATION = "waiting_forecast_use_saved_location"

# Состояния сценария сравнения
WAITING_COMPARE_CITY_1 = "waiting_compare_city_1"
WAITING_COMPARE_CITY_2 = "waiting_compare_city_2"
WAITING_COMPARE_LOCATION_PICK = "waiting_compare_location_pick"

# Состояния сценария уведомлений
ALERTS_MENU = "alerts_menu"
WAITING_ALERTS_SUBSCRIPTION_MENU = "waiting_alerts_subscription_menu"
WAITING_ALERTS_ADD_MENU = "waiting_alerts_add_menu"
WAITING_ALERTS_ADD_TEXT = "waiting_alerts_add_text"
WAITING_ALERTS_ADD_PICK = "waiting_alerts_add_pick"
WAITING_ALERTS_ADD_GEO = "waiting_alerts_add_geo"
WAITING_ALERTS_ADD_SAVED_PICK = "waiting_alerts_add_saved_pick"
WAITING_ALERTS_TOGGLE_PICK = "waiting_alerts_toggle_pick"
WAITING_ALERTS_INTERVAL_PICK = "waiting_alerts_interval_pick"
WAITING_ALERTS_INTERVAL_VALUE = "waiting_alerts_interval_value"
WAITING_ALERTS_DELETE_PICK = "waiting_alerts_delete_pick"

# Состояния сценария «Мои локации»
LOCATIONS_MENU = "locations_menu"
WAITING_LOCATION_TITLE = "waiting_location_title"
WAITING_NEW_SAVED_LOCATION_MENU = "waiting_new_saved_location_menu"
WAITING_NEW_SAVED_LOCATION_TEXT = "waiting_new_saved_location_text"
WAITING_NEW_SAVED_LOCATION_PICK = "waiting_new_saved_location_pick"
WAITING_NEW_SAVED_LOCATION_GEO = "waiting_new_saved_location_geo"
WAITING_NEW_SAVED_LOCATION_TITLE = "waiting_new_saved_location_title"
WAITING_RENAME_LOCATION_TITLE = "waiting_rename_location_title"


CURRENT_STATES = {
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_CURRENT_WEATHER_PICK,
}

DETAILS_STATES = {
    WAITING_DETAILS_CITY,
    WAITING_DETAILS_PICK,
    WAITING_DETAILS_USE_SAVED_LOCATION,
}

FORECAST_STATES = {
    WAITING_FORECAST_CITY,
    WAITING_FORECAST_PICK,
    WAITING_FORECAST_USE_SAVED_LOCATION,
}

COMPARE_STATES = {
    WAITING_COMPARE_CITY_1,
    WAITING_COMPARE_CITY_2,
    WAITING_COMPARE_LOCATION_PICK,
}

ALERTS_STATES = {
    ALERTS_MENU,
    WAITING_ALERTS_SUBSCRIPTION_MENU,
    WAITING_ALERTS_ADD_MENU,
    WAITING_ALERTS_ADD_TEXT,
    WAITING_ALERTS_ADD_PICK,
    WAITING_ALERTS_ADD_GEO,
    WAITING_ALERTS_ADD_SAVED_PICK,
    WAITING_ALERTS_TOGGLE_PICK,
    WAITING_ALERTS_INTERVAL_PICK,
    WAITING_ALERTS_INTERVAL_VALUE,
    WAITING_ALERTS_DELETE_PICK,
}

LOCATIONS_STATES = {
    LOCATIONS_MENU,
    WAITING_LOCATION_TITLE,
    WAITING_NEW_SAVED_LOCATION_MENU,
    WAITING_NEW_SAVED_LOCATION_TEXT,
    WAITING_NEW_SAVED_LOCATION_PICK,
    WAITING_NEW_SAVED_LOCATION_GEO,
    WAITING_NEW_SAVED_LOCATION_TITLE,
    WAITING_RENAME_LOCATION_TITLE,
}
