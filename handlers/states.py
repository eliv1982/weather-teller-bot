# Состояния сценария текущей погоды
WAITING_CURRENT_WEATHER_CITY = "waiting_current_weather_city"
WAITING_CURRENT_WEATHER_PICK = "waiting_current_weather_pick"
WAITING_CURRENT_WEATHER_COORDS = "waiting_current_weather_coords"
WAITING_CURRENT_WEATHER_GEO = "waiting_current_weather_geo"
WAITING_CURRENT_USE_FAVORITE = "waiting_current_use_favorite"

# Состояния сценария геолокации
WAITING_GEO_LOCATION = "waiting_geo_location"

# Состояния сценария расширенных данных
WAITING_DETAILS_CITY = "waiting_details_city"
WAITING_DETAILS_PICK = "waiting_details_pick"
WAITING_DETAILS_COORDS = "waiting_details_coords"
WAITING_DETAILS_GEO = "waiting_details_geo"
WAITING_DETAILS_USE_FAVORITE = "waiting_details_use_favorite"
WAITING_DETAILS_USE_SAVED_LOCATION = "waiting_details_use_saved_location"

# Состояния сценария прогноза
WAITING_FORECAST_CITY = "waiting_forecast_city"
WAITING_FORECAST_PICK = "waiting_forecast_pick"
WAITING_FORECAST_COORDS = "waiting_forecast_coords"
WAITING_FORECAST_GEO = "waiting_forecast_geo"
WAITING_FORECAST_USE_FAVORITE = "waiting_forecast_use_favorite"
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
WAITING_ALERTS_ADD_COORDS = "waiting_alerts_add_coords"
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
WAITING_AI_COMPARE_MODE = "waiting_ai_compare_mode"
WAITING_AI_COMPARE_LOC1_METHOD = "waiting_ai_compare_loc1_method"
WAITING_AI_COMPARE_LOC1_TEXT = "waiting_ai_compare_loc1_text"
WAITING_AI_COMPARE_LOC1_COORDS = "waiting_ai_compare_loc1_coords"
WAITING_AI_COMPARE_LOC1_GEO = "waiting_ai_compare_loc1_geo"
WAITING_AI_COMPARE_LOC1_PICK = "waiting_ai_compare_loc1_pick"
WAITING_AI_COMPARE_LOC1_SAVED_PICK = "waiting_ai_compare_loc1_saved_pick"
WAITING_AI_COMPARE_LOC2_METHOD = "waiting_ai_compare_loc2_method"
WAITING_AI_COMPARE_LOC2_TEXT = "waiting_ai_compare_loc2_text"
WAITING_AI_COMPARE_LOC2_COORDS = "waiting_ai_compare_loc2_coords"
WAITING_AI_COMPARE_LOC2_GEO = "waiting_ai_compare_loc2_geo"
WAITING_AI_COMPARE_LOC2_PICK = "waiting_ai_compare_loc2_pick"
WAITING_AI_COMPARE_LOC2_SAVED_PICK = "waiting_ai_compare_loc2_saved_pick"
WAITING_AI_COMPARE_DATE_PICK = "waiting_ai_compare_date_pick"


CURRENT_STATES = {
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_CURRENT_WEATHER_PICK,
    WAITING_CURRENT_WEATHER_COORDS,
    WAITING_CURRENT_WEATHER_GEO,
    WAITING_CURRENT_USE_FAVORITE,
}

DETAILS_STATES = {
    WAITING_DETAILS_CITY,
    WAITING_DETAILS_PICK,
    WAITING_DETAILS_COORDS,
    WAITING_DETAILS_GEO,
    WAITING_DETAILS_USE_FAVORITE,
    WAITING_DETAILS_USE_SAVED_LOCATION,
}

FORECAST_STATES = {
    WAITING_FORECAST_CITY,
    WAITING_FORECAST_PICK,
    WAITING_FORECAST_COORDS,
    WAITING_FORECAST_GEO,
    WAITING_FORECAST_USE_FAVORITE,
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
    WAITING_ALERTS_ADD_COORDS,
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
    WAITING_AI_COMPARE_MODE,
    WAITING_AI_COMPARE_LOC1_METHOD,
    WAITING_AI_COMPARE_LOC1_TEXT,
    WAITING_AI_COMPARE_LOC1_COORDS,
    WAITING_AI_COMPARE_LOC1_GEO,
    WAITING_AI_COMPARE_LOC1_PICK,
    WAITING_AI_COMPARE_LOC1_SAVED_PICK,
    WAITING_AI_COMPARE_LOC2_METHOD,
    WAITING_AI_COMPARE_LOC2_TEXT,
    WAITING_AI_COMPARE_LOC2_COORDS,
    WAITING_AI_COMPARE_LOC2_GEO,
    WAITING_AI_COMPARE_LOC2_PICK,
    WAITING_AI_COMPARE_LOC2_SAVED_PICK,
    WAITING_AI_COMPARE_DATE_PICK,
}
