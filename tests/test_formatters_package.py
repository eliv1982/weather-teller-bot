"""
Backward-compatibility and direct-import smoke tests for the formatters package.

These tests verify that:
1. All public names still importable from top-level `formatters` (as before).
2. Direct sub-module imports from formatters.* work correctly.
3. Selected callables return the expected type (str) on minimal valid input.
"""

import importlib


# ---------------------------------------------------------------------------
# 1. Top-level backward-compatibility: all legacy imports must resolve
# ---------------------------------------------------------------------------

class TestTopLevelImports:
    """Every public name that callers import from `formatters` must still work."""

    def test_help_text(self):
        from formatters import help_text
        assert callable(help_text)

    def test_format_saved_locations(self):
        from formatters import format_saved_locations
        assert callable(format_saved_locations)

    def test_format_alerts_status(self):
        from formatters import format_alerts_status
        assert callable(format_alerts_status)

    def test_format_alert_subscriptions(self):
        from formatters import format_alert_subscriptions
        assert callable(format_alert_subscriptions)

    def test_format_weather_response(self):
        from formatters import format_weather_response
        assert callable(format_weather_response)

    def test_format_details_response(self):
        from formatters import format_details_response
        assert callable(format_details_response)

    def test_format_tomorrow_forecast_response(self):
        from formatters import format_tomorrow_forecast_response
        assert callable(format_tomorrow_forecast_response)

    def test_format_today_forecast_response(self):
        from formatters import format_today_forecast_response
        assert callable(format_today_forecast_response)

    def test_format_compare_response(self):
        from formatters import format_compare_response
        assert callable(format_compare_response)

    def test_build_history_brief_summary(self):
        from formatters import build_history_brief_summary
        assert callable(build_history_brief_summary)

    def test_format_history_weather_response(self):
        from formatters import format_history_weather_response
        assert callable(format_history_weather_response)

    def test_build_monthly_climate_brief_summary(self):
        from formatters import build_monthly_climate_brief_summary
        assert callable(build_monthly_climate_brief_summary)

    def test_format_history_monthly_climate_response(self):
        from formatters import format_history_monthly_climate_response
        assert callable(format_history_monthly_climate_response)

    def test_format_source_compare_response(self):
        from formatters import format_source_compare_response
        assert callable(format_source_compare_response)

    def test_format_source_compare_current_response(self):
        from formatters import format_source_compare_current_response
        assert callable(format_source_compare_current_response)

    def test_wind_direction_ru(self):
        from formatters import wind_direction_ru
        assert callable(wind_direction_ru)


# ---------------------------------------------------------------------------
# 2. Direct sub-module imports smoke tests
# ---------------------------------------------------------------------------

class TestDirectSubmoduleImports:
    """Direct imports from formatters.* sub-modules must also resolve."""

    def test_weather_submodule(self):
        from formatters.weather import format_weather_response, format_details_response
        assert callable(format_weather_response)
        assert callable(format_details_response)

    def test_forecast_submodule(self):
        from formatters.forecast import (
            format_tomorrow_forecast_response,
            format_today_forecast_response,
            format_compare_response,
        )
        assert callable(format_tomorrow_forecast_response)
        assert callable(format_today_forecast_response)
        assert callable(format_compare_response)

    def test_history_submodule(self):
        from formatters.history import (
            build_history_brief_summary,
            format_history_weather_response,
            build_monthly_climate_brief_summary,
            format_history_monthly_climate_response,
        )
        assert callable(build_history_brief_summary)
        assert callable(format_history_weather_response)
        assert callable(build_monthly_climate_brief_summary)
        assert callable(format_history_monthly_climate_response)

    def test_source_compare_submodule(self):
        from formatters.source_compare import (
            format_source_compare_response,
            format_source_compare_current_response,
        )
        assert callable(format_source_compare_response)
        assert callable(format_source_compare_current_response)

    def test_common_submodule(self):
        from formatters.common import wind_direction_ru, _wind_text_from_values
        assert callable(wind_direction_ru)
        assert callable(_wind_text_from_values)


# ---------------------------------------------------------------------------
# 3. Identity: top-level name is the same object as sub-module name
# ---------------------------------------------------------------------------

class TestIdentity:
    """Top-level re-exports must point to the same object as sub-module functions."""

    def test_format_weather_response_identity(self):
        from formatters import format_weather_response as top
        from formatters.weather import format_weather_response as sub
        assert top is sub

    def test_format_history_weather_response_identity(self):
        from formatters import format_history_weather_response as top
        from formatters.history import format_history_weather_response as sub
        assert top is sub

    def test_format_source_compare_response_identity(self):
        from formatters import format_source_compare_response as top
        from formatters.source_compare import format_source_compare_response as sub
        assert top is sub


# ---------------------------------------------------------------------------
# 4. Minimal callable smoke tests (returns str, doesn't crash)
# ---------------------------------------------------------------------------

class TestMinimalCallable:
    """Spot-check that selected functions return str on minimal valid input."""

    def test_help_text_returns_str(self):
        from formatters import help_text
        result = help_text()
        assert isinstance(result, str)
        assert "/start" in result

    def test_wind_direction_ru_returns_str(self):
        from formatters import wind_direction_ru
        assert wind_direction_ru(0) == "северный"
        assert wind_direction_ru(180) == "южный"

    def test_format_saved_locations_empty(self):
        from formatters import format_saved_locations
        result = format_saved_locations({})
        assert isinstance(result, str)
        assert "пока нет" in result

    def test_format_alerts_status_defaults(self):
        from formatters import format_alerts_status
        result = format_alerts_status({})
        assert isinstance(result, str)
        assert "Уведомления" in result

    def test_build_history_brief_summary_minimal(self):
        from formatters import build_history_brief_summary
        result = build_history_brief_summary({"temperature_mean": 15.0})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_source_compare_response_minimal(self):
        from formatters import format_source_compare_response
        result = format_source_compare_response("Москва", {}, {})
        assert isinstance(result, str)
        assert "Москва" in result

    def test_format_source_compare_current_response_minimal(self):
        from formatters import format_source_compare_current_response
        result = format_source_compare_current_response("Москва", {}, {})
        assert isinstance(result, str)
        assert "Москва" in result
