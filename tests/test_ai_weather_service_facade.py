import importlib
import sys
import types


def _import_service_with_stubbed_postgres(monkeypatch):
    fake_pg = types.ModuleType("postgres_storage")
    fake_pg.get_ai_cached_response = lambda cache_key: None
    fake_pg.save_ai_cached_response = lambda cache_key, scenario, text, ttl_seconds: None
    monkeypatch.setitem(sys.modules, "postgres_storage", fake_pg)
    sys.modules.pop("ai_weather_service", None)
    module = importlib.import_module("ai_weather_service")
    return module.AiWeatherService


def test_ai_weather_service_public_facade_and_fallback_paths(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    public_methods = [
        "apply_location_alias",
        "assist_location_query",
        "explain_current_weather",
        "summarize_day_forecast",
        "explain_weather_details",
        "explain_weather_alert",
        "compare_two_locations_current_with_ai",
        "compare_two_locations_forecast_day_with_ai",
    ]
    for method_name in public_methods:
        assert hasattr(service, method_name)

    monkeypatch.setattr(service, "_get_cached", lambda cache_key: None)
    monkeypatch.setattr(service, "_save_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_call_model", lambda prompt, max_output_tokens=None: None)

    current = service.explain_current_weather(
        "Москва",
        {"main": {"temp": 7, "feels_like": 5}, "wind": {"speed": 2}, "weather": [{"description": "облачно"}]},
    )
    assert isinstance(current, str) and current.strip()

    forecast = service.summarize_day_forecast(
        "Москва",
        [
            {"dt_txt": "2026-01-01 09:00:00", "main": {"temp": 5}, "weather": [{"description": "ясно"}]},
            {"dt_txt": "2026-01-01 12:00:00", "main": {"temp": 8}, "weather": [{"description": "дождь"}]},
        ],
    )
    assert isinstance(forecast, str) and forecast.strip()

    details = service.explain_weather_details(
        "Москва",
        {"main": {"humidity": 60, "temp": 8}, "wind": {"speed": 3}, "visibility": 10000, "weather": [{"description": "ясно"}]},
        {"pm2_5": 12.0},
    )
    assert isinstance(details, str) and details.strip()

    alert = service.explain_weather_alert(
        "Москва",
        {"event_type": "precipitation", "description": "дождь", "slot_local": "12:00", "precip_probability": 0.8, "wind_speed": 4},
    )
    assert isinstance(alert, str) and alert.strip()

    assist = service.assist_location_query("питер", {"scenario": "current", "language": "ru"})
    assert isinstance(assist, dict) and assist

    compare_current = service.compare_two_locations_current_with_ai(
        {"city_label": "Москва", "temperature": 9, "feels_like": 8, "description": "ясно", "humidity": 50, "wind_speed": 2},
        {"city_label": "Сочи", "temperature": 14, "feels_like": 14, "description": "дождь", "humidity": 70, "wind_speed": 5},
    )
    assert isinstance(compare_current, str) and compare_current.strip()

    compare_day = service.compare_two_locations_forecast_day_with_ai(
        {
            "city_label": "Москва",
            "min_temp": 2,
            "max_temp": 10,
            "dominant_description": "дождь",
            "precipitation_signal": {"max_pop": 0.7, "rain_slots": 2},
            "wind_signal": {"avg_speed": 4, "max_speed": 7},
        },
        {
            "city_label": "Сочи",
            "min_temp": 8,
            "max_temp": 16,
            "dominant_description": "ясно",
            "precipitation_signal": {"max_pop": 0.1, "rain_slots": 0},
            "wind_signal": {"avg_speed": 2, "max_speed": 4},
        },
        "2026-01-01",
    )
    assert isinstance(compare_day, str) and compare_day.strip()

