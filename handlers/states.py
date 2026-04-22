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
WAITING_ALERTS_INTERVAL = "waiting_alerts_interval"
WAITING_ALERTS_LOCATION_MENU = "waiting_alerts_location_menu"
WAITING_ALERTS_LOCATION_TEXT = "waiting_alerts_location_text"
WAITING_ALERTS_LOCATION_PICK = "waiting_alerts_location_pick"
WAITING_ALERTS_LOCATION_GEO = "waiting_alerts_location_geo"

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
    WAITING_ALERTS_INTERVAL,
    WAITING_ALERTS_LOCATION_MENU,
    WAITING_ALERTS_LOCATION_TEXT,
    WAITING_ALERTS_LOCATION_PICK,
    WAITING_ALERTS_LOCATION_GEO,
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
