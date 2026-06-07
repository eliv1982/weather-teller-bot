import importlib
import sys
import types

from ai import compare_render


def _import_service_with_stubbed_postgres(monkeypatch):
    fake_pg = types.ModuleType("postgres_storage")
    fake_pg.get_ai_cached_response = lambda cache_key: None
    fake_pg.save_ai_cached_response = lambda cache_key, scenario, text, ttl_seconds: None
    monkeypatch.setitem(sys.modules, "postgres_storage", fake_pg)
    sys.modules.pop("ai_weather_service", None)
    module = importlib.import_module("ai_weather_service")
    return module.AiWeatherService


def test_compare_render_module_matches_service_wrappers(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    current_payload_1 = {
        "city_label": "Москва",
        "temperature": 9,
        "feels_like": 8,
        "description": "ясно",
        "humidity": 50,
        "wind_speed": 2,
    }
    current_payload_2 = {
        "city_label": "Сочи",
        "temperature": 14,
        "feels_like": 14,
        "description": "дождь",
        "humidity": 70,
        "wind_speed": 5,
    }
    assert compare_render._render_compare_current_factual(service, current_payload_1, current_payload_2) == (
        service._render_compare_current_factual(current_payload_1, current_payload_2)
    )

    forecast_payload_1 = {
        "city_label": "Москва",
        "min_temp": 2,
        "max_temp": 10,
        "dominant_description": "дождь",
        "precipitation_signal": {"max_pop": 0.7, "rain_slots": 2},
        "wind_signal": {"avg_speed": 4, "max_speed": 7},
    }
    forecast_payload_2 = {
        "city_label": "Сочи",
        "min_temp": 8,
        "max_temp": 16,
        "dominant_description": "ясно",
        "precipitation_signal": {"max_pop": 0.1, "rain_slots": 0},
        "wind_signal": {"avg_speed": 2, "max_speed": 4},
    }
    assert compare_render._render_compare_forecast_factual(
        service,
        forecast_payload_1,
        forecast_payload_2,
        "2026-01-01",
    ) == service._render_compare_forecast_factual(forecast_payload_1, forecast_payload_2, "2026-01-01")
