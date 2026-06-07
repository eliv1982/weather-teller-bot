"""
Callback data constants for all inline keyboard buttons.

Rules:
- Static values (full callback_data) are plain string constants.
- Dynamic values built with f-strings keep a *_PREFIX constant for the
  prefix part; callers concatenate :{payload} themselves, e.g.
      f"{FORECAST_DAY_PREFIX}:{day}"
- String values are byte-for-byte identical to what handlers expect.
  Do NOT change values — only keyboards.py generation uses these; handler
  matching logic is untouched in this refactor step.
"""

# ---------------------------------------------------------------------------
# Yes / No
# ---------------------------------------------------------------------------
YN_YES = "yn_yes"
YN_NO = "yn_no"
YN_MENU = "yn_menu"

# ---------------------------------------------------------------------------
# Current weather
# ---------------------------------------------------------------------------
CURRENT_PICK_PREFIX = "current_pick"
CURRENT_SAVED_PICK_PREFIX = "current_saved_pick"
CURRENT_CANCEL = "current_cancel"

# ---------------------------------------------------------------------------
# Details (extended data)
# ---------------------------------------------------------------------------
DETAILS_PICK_PREFIX = "details_pick"
DETAILS_SAVED_PICK_PREFIX = "details_saved_pick"
DETAILS_CANCEL = "details_cancel"

# ---------------------------------------------------------------------------
# Forecast (5-day / today / tomorrow)
# ---------------------------------------------------------------------------
FORECAST_PICK_PREFIX = "forecast_pick"
FORECAST_SAVED_PICK_PREFIX = "forecast_saved_pick"
FORECAST_DAY_PREFIX = "forecast_day"
FORECAST_BACK = "forecast_back"
FORECAST_MENU = "forecast_menu"
FORECAST_CANCEL = "forecast_cancel"

# AI forecast day explanations
AI_FORECAST_DAY_PREFIX = "ai_forecast_day"
AI_TODAY_FORECAST_DAY_PREFIX = "ai_today_forecast_day"
AI_TOMORROW_FORECAST_DAY_PREFIX = "ai_tomorrow_forecast_day"

# ---------------------------------------------------------------------------
# Compare (deterministic 2-city)
# ---------------------------------------------------------------------------
COMPARE_PICK_PREFIX = "compare_pick"
COMPARE_CANCEL = "compare_cancel"

# ---------------------------------------------------------------------------
# Source compare (OpenWeather vs Open-Meteo)
# ---------------------------------------------------------------------------
SOURCE_COMPARE_PICK_PREFIX = "source_compare_pick"
SOURCE_COMPARE_SAVED_PICK_PREFIX = "source_compare_saved_pick"
SOURCE_COMPARE_DATE_PICK_PREFIX = "source_compare_date_pick"
SOURCE_COMPARE_DATE_CANCEL = "source_compare_date_cancel"
SOURCE_COMPARE_DATE_ANOTHER = "source_compare_date_another"
SOURCE_COMPARE_CANCEL = "source_compare_cancel"

# ---------------------------------------------------------------------------
# History (daily archive + climate normals)
# ---------------------------------------------------------------------------
HISTORY_SECTION_PREFIX = "history_section"
HISTORY_PICK_PREFIX = "history_pick"
HISTORY_SAVED_PICK_PREFIX = "history_saved_pick"
HISTORY_DATE_PRESET_PREFIX = "history_date_preset"
HISTORY_DATE_CUSTOM = "history_date_custom"
HISTORY_DATE_YEAR_PREFIX = "history_date_year"
HISTORY_CLIMATE_MODE_PREFIX = "history_climate_mode"
HISTORY_CLIMATE_MONTH_PREFIX = "history_climate_month"
HISTORY_CLIMATE_BACK_TO_ACTIONS = "history_climate_back_to_actions"
HISTORY_CLIMATE_BACK_TO_MODES = "history_climate_back_to_modes"
HISTORY_CLIMATE_OPEN = "history_climate_open"
HISTORY_MENU = "history_menu"
HISTORY_CANCEL = "history_cancel"

# History section payload values
HISTORY_SECTION_DAILY = "daily"
HISTORY_SECTION_CLIMATE = "climate"

# History date preset payload values
HISTORY_PRESET_YESTERDAY = "yesterday"
HISTORY_PRESET_7D = "7d"
HISTORY_PRESET_30D = "30d"

# History climate mode payload values
HISTORY_CLIMATE_MODE_MONTHLY_YEAR = "monthly_year"
HISTORY_CLIMATE_MODE_MONTHLY_NORMALS = "monthly_normals"

# ---------------------------------------------------------------------------
# AI compare (two saved locations)
# ---------------------------------------------------------------------------
AICMP_SAVED_PICK_PREFIX = "aicmp_saved_pick"
AICMP_GEO_PICK_PREFIX = "aicmp_geo_pick"
AICMP_DATE_PICK_PREFIX = "aicmp_date_pick"
AICMP_SAVED_CANCEL = "aicmp_saved_cancel"
AICMP_GEO_CANCEL = "aicmp_geo_cancel"
AICMP_DATE_CANCEL = "aicmp_date_cancel"
AICMP_DATE_ANOTHER = "aicmp_date_another"

# ---------------------------------------------------------------------------
# Saved locations management
# ---------------------------------------------------------------------------
SAVEDLOC_PICK_PREFIX = "savedloc_pick"
SAVEDLOC_CANCEL = "savedloc_cancel"
FAVORITE_PICK_PREFIX = "favorite_pick"
DELETE_LOCATION_PICK_PREFIX = "delete_location_pick"
RENAME_LOCATION_PICK_PREFIX = "rename_location_pick"

# ---------------------------------------------------------------------------
# Alert subscriptions
# ---------------------------------------------------------------------------
ALERTS_ADD_PICK_PREFIX = "alerts_add_pick"
ALERTS_SUB_ADD_SAVED_PREFIX = "alerts_sub_add_saved"
ALERTS_SUB_TOGGLE_PREFIX = "alerts_sub_toggle"
ALERTS_SUB_INTERVAL_PREFIX = "alerts_sub_interval"
ALERTS_SUB_DELETE_PREFIX = "alerts_sub_delete"
ALERTS_ADD_CANCEL = "alerts_add_cancel"

# ---------------------------------------------------------------------------
# AI explanations (current / details)
# ---------------------------------------------------------------------------
AI_CURRENT_EXPLAIN = "ai_current_explain"
AI_CURRENT_EXPLAIN_PREFIX = "ai_current_explain"
AI_DETAILS_EXPLAIN = "ai_details_explain"
AI_DETAILS_EXPLAIN_PREFIX = "ai_details_explain"
