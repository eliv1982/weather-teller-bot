"""
Sanity tests for callbacks/constants.py.

Goal: verify that key constants equal the exact string values that handlers
expect. If a constant is ever accidentally changed, these tests will catch it
before the change reaches production and breaks inline button routing.

Coverage strategy:
- One test per domain group (yes/no, forecast, history, etc.).
- Static full-value constants are checked directly.
- Prefix constants are verified by asserting that a concrete composed
  callback_data (prefix + separator + payload) matches the expected literal.
- We do NOT snapshot the entire file — only the strings that are actually
  matched by handlers (startswith / == checks in bot.py and callbacks_*.py).
"""

import pytest
from callbacks.constants import (
    # yes/no
    YN_YES, YN_NO, YN_MENU,
    # current weather
    CURRENT_PICK_PREFIX, CURRENT_SAVED_PICK_PREFIX, CURRENT_CANCEL,
    # details
    DETAILS_PICK_PREFIX, DETAILS_SAVED_PICK_PREFIX, DETAILS_CANCEL,
    # forecast
    FORECAST_PICK_PREFIX, FORECAST_DAY_PREFIX, FORECAST_BACK,
    FORECAST_MENU, FORECAST_CANCEL,
    AI_FORECAST_DAY_PREFIX,
    # compare
    COMPARE_PICK_PREFIX, COMPARE_CANCEL,
    # source compare
    SOURCE_COMPARE_PICK_PREFIX, SOURCE_COMPARE_DATE_PICK_PREFIX,
    SOURCE_COMPARE_DATE_CANCEL, SOURCE_COMPARE_DATE_ANOTHER,
    SOURCE_COMPARE_CANCEL,
    # history
    HISTORY_SECTION_PREFIX, HISTORY_SECTION_DAILY, HISTORY_SECTION_CLIMATE,
    HISTORY_PICK_PREFIX, HISTORY_SAVED_PICK_PREFIX,
    HISTORY_DATE_PRESET_PREFIX, HISTORY_DATE_CUSTOM, HISTORY_DATE_YEAR_PREFIX,
    HISTORY_CLIMATE_MODE_PREFIX,
    HISTORY_CLIMATE_MODE_MONTHLY_YEAR, HISTORY_CLIMATE_MODE_MONTHLY_NORMALS,
    HISTORY_CLIMATE_MONTH_PREFIX,
    HISTORY_CLIMATE_BACK_TO_ACTIONS, HISTORY_CLIMATE_BACK_TO_MODES,
    HISTORY_MENU, HISTORY_CANCEL,
    HISTORY_PRESET_YESTERDAY, HISTORY_PRESET_7D, HISTORY_PRESET_30D,
    # ai compare
    AICMP_GEO_PICK_PREFIX, AICMP_SAVED_PICK_PREFIX, AICMP_DATE_PICK_PREFIX,
    AICMP_GEO_CANCEL, AICMP_SAVED_CANCEL, AICMP_DATE_CANCEL, AICMP_DATE_ANOTHER,
    # saved locations
    FAVORITE_PICK_PREFIX, DELETE_LOCATION_PICK_PREFIX, RENAME_LOCATION_PICK_PREFIX,
    # alerts
    ALERTS_ADD_PICK_PREFIX, ALERTS_SUB_ADD_SAVED_PREFIX,
    ALERTS_SUB_TOGGLE_PREFIX, ALERTS_SUB_INTERVAL_PREFIX,
    ALERTS_SUB_DELETE_PREFIX, ALERTS_ADD_CANCEL,
    # ai explain
    AI_CURRENT_EXPLAIN, AI_CURRENT_EXPLAIN_PREFIX,
    AI_DETAILS_EXPLAIN, AI_DETAILS_EXPLAIN_PREFIX,
    AI_TOMORROW_FORECAST_DAY_PREFIX,
    AI_TODAY_FORECAST_DAY_PREFIX,
    # source compare (saved pick)
    SOURCE_COMPARE_SAVED_PICK_PREFIX,
    # forecast (saved pick)
    FORECAST_SAVED_PICK_PREFIX,
    # history climate open
    HISTORY_CLIMATE_OPEN,
)


class TestYesNoConstants:
    def test_yn_yes(self):
        assert YN_YES == "yn_yes"

    def test_yn_no(self):
        assert YN_NO == "yn_no"

    def test_yn_menu(self):
        assert YN_MENU == "yn_menu"


class TestCurrentWeatherConstants:
    def test_current_pick_prefix(self):
        assert CURRENT_PICK_PREFIX == "current_pick"
        assert f"{CURRENT_PICK_PREFIX}:0" == "current_pick:0"

    def test_current_saved_pick_prefix(self):
        assert CURRENT_SAVED_PICK_PREFIX == "current_saved_pick"
        assert f"{CURRENT_SAVED_PICK_PREFIX}:loc1" == "current_saved_pick:loc1"

    def test_current_cancel(self):
        assert CURRENT_CANCEL == "current_cancel"


class TestDetailsConstants:
    def test_details_pick_prefix(self):
        assert DETAILS_PICK_PREFIX == "details_pick"
        assert f"{DETAILS_PICK_PREFIX}:2" == "details_pick:2"

    def test_details_saved_pick_prefix(self):
        assert DETAILS_SAVED_PICK_PREFIX == "details_saved_pick"

    def test_details_cancel(self):
        assert DETAILS_CANCEL == "details_cancel"


class TestForecastConstants:
    def test_forecast_pick_prefix(self):
        assert FORECAST_PICK_PREFIX == "forecast_pick"

    def test_forecast_day_prefix_composition(self):
        assert f"{FORECAST_DAY_PREFIX}:10.06.2025" == "forecast_day:10.06.2025"

    def test_forecast_back(self):
        assert FORECAST_BACK == "forecast_back"

    def test_forecast_menu(self):
        assert FORECAST_MENU == "forecast_menu"

    def test_forecast_cancel(self):
        assert FORECAST_CANCEL == "forecast_cancel"

    def test_forecast_saved_pick_prefix(self):
        assert FORECAST_SAVED_PICK_PREFIX == "forecast_saved_pick"
        assert f"{FORECAST_SAVED_PICK_PREFIX}:loc-uuid" == "forecast_saved_pick:loc-uuid"

    def test_ai_forecast_day_prefix_composition(self):
        assert f"{AI_FORECAST_DAY_PREFIX}:10.06.2025" == "ai_forecast_day:10.06.2025"


class TestCompareConstants:
    def test_compare_pick_prefix_with_step(self):
        assert f"{COMPARE_PICK_PREFIX}:1:0" == "compare_pick:1:0"
        assert f"{COMPARE_PICK_PREFIX}:2:3" == "compare_pick:2:3"

    def test_compare_cancel(self):
        assert COMPARE_CANCEL == "compare_cancel"


class TestSourceCompareConstants:
    def test_source_compare_pick_prefix(self):
        assert SOURCE_COMPARE_PICK_PREFIX == "source_compare_pick"

    def test_source_compare_date_pick_prefix_composition(self):
        assert f"{SOURCE_COMPARE_DATE_PICK_PREFIX}:10.06.2025" == "source_compare_date_pick:10.06.2025"

    def test_source_compare_date_cancel(self):
        assert SOURCE_COMPARE_DATE_CANCEL == "source_compare_date_cancel"

    def test_source_compare_date_another(self):
        assert SOURCE_COMPARE_DATE_ANOTHER == "source_compare_date_another"

    def test_source_compare_cancel(self):
        assert SOURCE_COMPARE_CANCEL == "source_compare_cancel"

    def test_source_compare_saved_pick_prefix(self):
        assert SOURCE_COMPARE_SAVED_PICK_PREFIX == "source_compare_saved_pick"
        assert f"{SOURCE_COMPARE_SAVED_PICK_PREFIX}:loc-uuid" == "source_compare_saved_pick:loc-uuid"


class TestHistoryConstants:
    def test_history_section_daily_composition(self):
        assert f"{HISTORY_SECTION_PREFIX}:{HISTORY_SECTION_DAILY}" == "history_section:daily"

    def test_history_section_climate_composition(self):
        assert f"{HISTORY_SECTION_PREFIX}:{HISTORY_SECTION_CLIMATE}" == "history_section:climate"

    def test_history_pick_prefix(self):
        assert HISTORY_PICK_PREFIX == "history_pick"

    def test_history_saved_pick_prefix(self):
        assert HISTORY_SAVED_PICK_PREFIX == "history_saved_pick"

    def test_history_date_preset_yesterday(self):
        assert f"{HISTORY_DATE_PRESET_PREFIX}:{HISTORY_PRESET_YESTERDAY}" == "history_date_preset:yesterday"

    def test_history_date_preset_7d(self):
        assert f"{HISTORY_DATE_PRESET_PREFIX}:{HISTORY_PRESET_7D}" == "history_date_preset:7d"

    def test_history_date_preset_30d(self):
        assert f"{HISTORY_DATE_PRESET_PREFIX}:{HISTORY_PRESET_30D}" == "history_date_preset:30d"

    def test_history_date_custom(self):
        assert HISTORY_DATE_CUSTOM == "history_date_custom"

    def test_history_date_year_prefix_composition(self):
        assert f"{HISTORY_DATE_YEAR_PREFIX}:2025-06-10" == "history_date_year:2025-06-10"

    def test_history_climate_mode_monthly_year(self):
        assert f"{HISTORY_CLIMATE_MODE_PREFIX}:{HISTORY_CLIMATE_MODE_MONTHLY_YEAR}" == "history_climate_mode:monthly_year"

    def test_history_climate_mode_monthly_normals(self):
        assert f"{HISTORY_CLIMATE_MODE_PREFIX}:{HISTORY_CLIMATE_MODE_MONTHLY_NORMALS}" == "history_climate_mode:monthly_normals"

    def test_history_climate_month_prefix_composition(self):
        for month_num in range(1, 13):
            composed = f"{HISTORY_CLIMATE_MONTH_PREFIX}:{month_num}"
            assert composed == f"history_climate_month:{month_num}"

    def test_history_climate_back_to_actions(self):
        assert HISTORY_CLIMATE_BACK_TO_ACTIONS == "history_climate_back_to_actions"

    def test_history_climate_back_to_modes(self):
        assert HISTORY_CLIMATE_BACK_TO_MODES == "history_climate_back_to_modes"

    def test_history_menu(self):
        assert HISTORY_MENU == "history_menu"

    def test_history_cancel(self):
        assert HISTORY_CANCEL == "history_cancel"

    def test_history_climate_open(self):
        assert HISTORY_CLIMATE_OPEN == "history_climate_open"


class TestAiCompareConstants:
    def test_aicmp_geo_pick_prefix_with_step(self):
        assert f"{AICMP_GEO_PICK_PREFIX}:1:0" == "aicmp_geo_pick:1:0"
        assert f"{AICMP_GEO_PICK_PREFIX}:2:3" == "aicmp_geo_pick:2:3"

    def test_aicmp_geo_cancel(self):
        assert AICMP_GEO_CANCEL == "aicmp_geo_cancel"

    def test_aicmp_saved_pick_prefix_with_step(self):
        assert f"{AICMP_SAVED_PICK_PREFIX}:1:loc-uuid" == "aicmp_saved_pick:1:loc-uuid"
        assert f"{AICMP_SAVED_PICK_PREFIX}:2:loc-uuid" == "aicmp_saved_pick:2:loc-uuid"

    def test_aicmp_date_pick_prefix_composition(self):
        assert f"{AICMP_DATE_PICK_PREFIX}:10.06.2025" == "aicmp_date_pick:10.06.2025"

    def test_aicmp_saved_cancel(self):
        assert AICMP_SAVED_CANCEL == "aicmp_saved_cancel"

    def test_aicmp_date_cancel(self):
        assert AICMP_DATE_CANCEL == "aicmp_date_cancel"

    def test_aicmp_date_another(self):
        assert AICMP_DATE_ANOTHER == "aicmp_date_another"


class TestSavedLocationsConstants:
    def test_favorite_pick_prefix_composition(self):
        assert f"{FAVORITE_PICK_PREFIX}:loc123" == "favorite_pick:loc123"

    def test_delete_location_pick_prefix(self):
        assert DELETE_LOCATION_PICK_PREFIX == "delete_location_pick"

    def test_rename_location_pick_prefix(self):
        assert RENAME_LOCATION_PICK_PREFIX == "rename_location_pick"


class TestAlertsConstants:
    def test_alerts_add_pick_prefix(self):
        assert ALERTS_ADD_PICK_PREFIX == "alerts_add_pick"

    def test_alerts_sub_add_saved_prefix(self):
        assert ALERTS_SUB_ADD_SAVED_PREFIX == "alerts_sub_add_saved"

    def test_alerts_sub_toggle_prefix_composition(self):
        assert f"{ALERTS_SUB_TOGGLE_PREFIX}:loc-id" == "alerts_sub_toggle:loc-id"

    def test_alerts_sub_interval_prefix(self):
        assert ALERTS_SUB_INTERVAL_PREFIX == "alerts_sub_interval"

    def test_alerts_sub_delete_prefix(self):
        assert ALERTS_SUB_DELETE_PREFIX == "alerts_sub_delete"

    def test_alerts_add_cancel(self):
        assert ALERTS_ADD_CANCEL == "alerts_add_cancel"


class TestAiExplainConstants:
    def test_ai_current_explain(self):
        assert AI_CURRENT_EXPLAIN == "ai_current_explain"

    def test_ai_current_explain_prefix_composition(self):
        assert f"{AI_CURRENT_EXPLAIN_PREFIX}:snap123" == "ai_current_explain:snap123"

    def test_ai_details_explain(self):
        assert AI_DETAILS_EXPLAIN == "ai_details_explain"

    def test_ai_details_explain_prefix_composition(self):
        assert f"{AI_DETAILS_EXPLAIN_PREFIX}:snap456" == "ai_details_explain:snap456"

    def test_ai_tomorrow_forecast_day_prefix_composition(self):
        assert f"{AI_TOMORROW_FORECAST_DAY_PREFIX}:10.06.2025" == "ai_tomorrow_forecast_day:10.06.2025"

    def test_ai_today_forecast_day_prefix_composition(self):
        assert f"{AI_TODAY_FORECAST_DAY_PREFIX}:10.06.2025" == "ai_today_forecast_day:10.06.2025"


class TestAllConstantsAreStrings:
    """Guard: every exported constant must be a plain str (no accidental int/None)."""

    def test_all_constants_are_str(self):
        from callbacks import constants
        import inspect

        for name, value in inspect.getmembers(constants):
            if name.startswith("_") or inspect.ismodule(value):
                continue
            assert isinstance(value, str), (
                f"callbacks.constants.{name} должен быть строкой, получен {type(value).__name__!r}"
            )
