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


def _monthly_normals_payload(**overrides):
    payload = {
        "mode": "monthly_normals",
        "month": 1,
        "month_label": "Январь",
        "month_label_lower": "январь",
        "reference_period": "1991-2020",
        "used_years_count": 24,
        "expected_years_count": 30,
        "temperature_month_mean": -3.0,
        "temperature_daily_max_mean": -1.0,
        "temperature_daily_min_mean": -6.0,
        "temperature_extreme_high_mean": 2.5,
        "temperature_extreme_low_mean": -10.5,
        "precipitation_month_sum": 42.0,
        "rain_month_sum": 18.0,
        "snowfall_month_sum": 20.0,
        "precipitation_days_mean": 12.4,
        "precipitation_days_share_mean": 0.40,
        "wind_daily_max_mean": 5.1,
        "wind_month_peak_mean": 10.2,
        "relative_humidity_mean": 80.0,
        "pressure_mean": 1015.0,
        "dominant_weather_description": "пасмурно",
    }
    payload.update(overrides)
    return payload


def test_ai_weather_service_public_facade_and_fallback_paths(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    public_methods = [
        "apply_location_alias",
        "assist_location_query",
        "explain_current_weather",
        "explain_history_weather",
        "explain_monthly_climate",
        "summarize_day_forecast",
        "explain_tomorrow_forecast",
        "explain_today_forecast",
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

    history = service.explain_history_weather(
        "Москва",
        {
            "date": "2026-05-01",
            "temperature_max": 8,
            "temperature_min": 2,
            "temperature_mean": 5,
            "precipitation_sum": 0.0,
            "rain_sum": 0.0,
            "snowfall_sum": 0.0,
            "wind_speed_max": 4,
            "relative_humidity_mean": 78,
            "pressure_mean": 1015,
            "weather_description": "пасмурно",
        },
    )
    assert isinstance(history, str) and history.strip()

    monthly = service.explain_monthly_climate("Москва", _monthly_normals_payload())
    assert isinstance(monthly, str) and monthly.strip()

    forecast = service.summarize_day_forecast(
        "Москва",
        [
            {"dt_txt": "2026-01-01 09:00:00", "main": {"temp": 5}, "weather": [{"description": "ясно"}]},
            {"dt_txt": "2026-01-01 12:00:00", "main": {"temp": 8}, "weather": [{"description": "дождь"}]},
        ],
    )
    assert isinstance(forecast, str) and forecast.strip()

    tomorrow = service.explain_tomorrow_forecast(
        "Москва",
        [
            {"dt_txt": "2026-01-02 09:00:00", "main": {"temp": 5, "feels_like": 3, "pressure": 1013}, "wind": {"speed": 2}, "weather": [{"description": "ясно"}]},
            {"dt_txt": "2026-01-02 12:00:00", "main": {"temp": 8, "feels_like": 7, "pressure": 1013}, "wind": {"speed": 4}, "weather": [{"description": "облачно"}]},
        ],
    )
    assert isinstance(tomorrow, str) and tomorrow.strip()

    today = service.explain_today_forecast(
        "Москва",
        [
            {
                "dt_txt": "2026-01-01 15:00:00",
                "main": {"temp": 6, "feels_like": 4, "pressure": 1012},
                "wind": {"speed": 5},
                "weather": [{"description": "небольшой дождь"}],
            }
        ],
        is_remaining_day=True,
    )
    assert isinstance(today, str) and today.strip()

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


def test_history_ai_postprocess_rewrites_raw_pressure_to_mmhg(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="test")

    monkeypatch.setattr(service, "_get_cached", lambda cache_key: None)
    monkeypatch.setattr(service, "_save_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        service,
        "_call_model",
        lambda prompt, max_output_tokens=None: (
            "По архивным данным день был пасмурным. Давление было около 1020.2. "
            "Ветер оставался слабым."
        ),
    )

    text = service.explain_history_weather(
        "Москва",
        {
            "date": "2026-05-01",
            "temperature_max": 8,
            "temperature_min": 2,
            "temperature_mean": 5,
            "precipitation_sum": 0.0,
            "rain_sum": 0.0,
            "snowfall_sum": 0.0,
            "wind_speed_max": 4,
            "relative_humidity_mean": 78,
            "pressure_mean": 1020.2,
            "weather_description": "пасмурно",
        },
    )

    assert "1020.2" not in text
    assert "765 мм рт. ст." in text
    assert "гПа" not in text


def test_compare_current_rejects_invalid_cached_text_and_stays_deterministic(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")
    saved = []
    cached_text = "Лучше выбрать Сочи: там спокойнее для прогулки."

    monkeypatch.setattr(service, "_get_cached", lambda cache_key: cached_text)
    monkeypatch.setattr(
        service,
        "_save_cached",
        lambda cache_key, scenario, text, ttl_seconds: saved.append(
            {"scenario": scenario, "text": text, "ttl_seconds": ttl_seconds}
        ),
    )
    monkeypatch.setattr(
        service,
        "_call_model",
        lambda prompt, max_output_tokens=None: (_ for _ in ()).throw(AssertionError("_call_model should not be used")),
    )

    text = service.compare_two_locations_current_with_ai(
        {"city_label": "Москва", "temperature": 9, "feels_like": 8, "description": "ясно", "humidity": 50, "wind_speed": 2},
        {"city_label": "Сочи", "temperature": 14, "feels_like": 14, "description": "дождь", "humidity": 70, "wind_speed": 5},
    )

    assert service._is_compare_text_factual(cached_text) is False
    assert service._is_compare_text_factual(text) is True
    assert "📍 Москва" in text
    assert "📍 Сочи" in text
    assert "Лучше" not in text
    assert saved == [{"scenario": "ai_compare_current", "text": text, "ttl_seconds": service.ttl_current_seconds}]


def test_compare_forecast_day_rejects_invalid_cached_text_and_stays_deterministic(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")
    saved = []
    cached_text = "У вариантов разные плюсы, выбирай Москву для прогулки."

    monkeypatch.setattr(service, "_get_cached", lambda cache_key: cached_text)
    monkeypatch.setattr(
        service,
        "_save_cached",
        lambda cache_key, scenario, text, ttl_seconds: saved.append(
            {"scenario": scenario, "text": text, "ttl_seconds": ttl_seconds}
        ),
    )
    monkeypatch.setattr(
        service,
        "_call_model",
        lambda prompt, max_output_tokens=None: (_ for _ in ()).throw(AssertionError("_call_model should not be used")),
    )
    monkeypatch.setattr(
        service,
        "_build_forecast_day_risk_profile",
        lambda payload: (_ for _ in ()).throw(AssertionError("_build_forecast_day_risk_profile should not be used")),
    )
    monkeypatch.setattr(
        service,
        "_build_forecast_compare_verdict",
        lambda profile_1, profile_2: (_ for _ in ()).throw(AssertionError("_build_forecast_compare_verdict should not be used")),
    )

    text = service.compare_two_locations_forecast_day_with_ai(
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

    assert service._is_compare_text_factual(cached_text) is False
    assert service._is_compare_text_factual(text) is True
    assert "📍 Москва" in text
    assert "📍 Сочи" in text
    assert "выбирай" not in text.lower()
    assert saved == [{"scenario": "ai_compare_forecast_day", "text": text, "ttl_seconds": service.ttl_forecast_seconds}]


def test_compare_forecast_day_cache_hit_skips_profile_and_verdict_helpers(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")
    cached_text = "📍 Москва\n📅 Дата: 2026-01-01\n\n✨ В локации Москва: ожидается прохладная погода."

    monkeypatch.setattr(service, "_get_cached", lambda cache_key: cached_text)
    monkeypatch.setattr(
        service,
        "_build_forecast_day_risk_profile",
        lambda payload: (_ for _ in ()).throw(AssertionError("_build_forecast_day_risk_profile should not be used")),
    )
    monkeypatch.setattr(
        service,
        "_build_forecast_compare_verdict",
        lambda profile_1, profile_2: (_ for _ in ()).throw(AssertionError("_build_forecast_compare_verdict should not be used")),
    )
    monkeypatch.setattr(
        service,
        "_call_model",
        lambda prompt, max_output_tokens=None: (_ for _ in ()).throw(AssertionError("_call_model should not be used")),
    )
    monkeypatch.setattr(
        service,
        "_save_cached",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("_save_cached should not be used")),
    )

    text = service.compare_two_locations_forecast_day_with_ai(
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

    assert text == cached_text


def test_explain_today_forecast_cache_hit_skips_model(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")
    cached_text = "Сегодня в локации Москва осадки заметны только местами."

    monkeypatch.setattr(service, "_get_cached", lambda cache_key: cached_text)
    monkeypatch.setattr(
        service,
        "_call_model",
        lambda prompt, max_output_tokens=None: (_ for _ in ()).throw(AssertionError("_call_model should not be used")),
    )
    monkeypatch.setattr(
        service,
        "_save_cached",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("_save_cached should not be used")),
    )

    text = service.explain_today_forecast(
        "Москва",
        [
            {
                "dt_txt": "2026-01-01 15:00:00",
                "main": {"temp": 6, "feels_like": 4, "pressure": 1012},
                "wind": {"speed": 5},
                "weather": [{"description": "небольшой дождь"}],
            }
        ],
        is_remaining_day=True,
    )

    assert text == cached_text


def test_explain_weather_alert_cache_hit_postprocesses_without_model(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")
    cached_text = "К вечеру короткий маршрут под крышей удобнее: ветер усиливает холод и сильно влияет на комфорт."

    monkeypatch.setattr(service, "_get_cached", lambda cache_key: cached_text)
    monkeypatch.setattr(
        service,
        "_call_model",
        lambda prompt, max_output_tokens=None: (_ for _ in ()).throw(AssertionError("_call_model should not be used")),
    )
    monkeypatch.setattr(
        service,
        "_save_cached",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("_save_cached should not be used")),
    )

    text = service.explain_weather_alert(
        "Москва",
        {"event_type": "precipitation", "description": "дождь", "slot_local": "12:00", "precip_probability": 0.8, "wind_speed": 4},
    )

    assert "короткий выход" in text
    assert "ветер делает воздух прохладнее" in text
    assert "заметно влияет на комфорт" in text
    assert "маршрут под крышей" not in text.lower()


def test_explain_monthly_climate_cache_hit_valid_skips_model_and_returns_postprocessed_text(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")
    cached_text = (
        "Это не прогноз на конкретный месяц, а архивная справка по данным за 1991-2020. "
        "Вероятности осадков в среднем невысоки. Давление было около 1015.0."
    )

    monkeypatch.setattr(service, "_get_cached", lambda cache_key: cached_text)
    monkeypatch.setattr(
        service,
        "_call_model",
        lambda prompt, max_output_tokens=None: (_ for _ in ()).throw(AssertionError("_call_model should not be used")),
    )
    monkeypatch.setattr(
        service,
        "_save_cached",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("_save_cached should not be used")),
    )

    text = service.explain_monthly_climate("Москва", _monthly_normals_payload())

    assert "Это архивная справка по данным за 1991-2020." in text
    assert "доля дней с осадками по архивным данным" in text
    assert "мм рт. ст." in text
    assert "прогноз" not in text.lower()


def test_explain_monthly_climate_invalid_cached_text_falls_back_without_model(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")
    fallback_text = "fallback monthly climate"

    monkeypatch.setattr(service, "_get_cached", lambda cache_key: "Это прогноз на конкретный месяц. Давление 1015 hPa.")
    monkeypatch.setattr(service, "_fallback_monthly_climate", lambda city_label, report_data: fallback_text)
    monkeypatch.setattr(
        service,
        "_call_model",
        lambda prompt, max_output_tokens=None: (_ for _ in ()).throw(AssertionError("_call_model should not be used")),
    )

    text = service.explain_monthly_climate("Москва", _monthly_normals_payload())

    assert text == fallback_text


def test_postprocess_monthly_climate_text_normalizes_probability_pressure_and_reference_phrase(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    text = service._postprocess_monthly_climate_text(
        (
            "Это не прогноз на конкретный месяц, а архивная справка по данным за 1991-2020. "
            "Вероятности осадков выше обычного. Давление было около 1015.0."
        ),
        _monthly_normals_payload(),
    )

    assert "Это архивная справка по данным за 1991-2020." in text
    assert "доля дней с осадками по архивным данным" in text
    assert "мм рт. ст." in text
    assert "1015.0" not in text


def test_postprocess_weather_alert_text_softens_route_and_comfort_phrases(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    text = service._postprocess_weather_alert_text(
        "К вечеру короткий маршрут под крышей удобнее: ветер усиливает холод и сильно влияет на комфорт."
    )

    assert "короткий выход" in text
    assert "ветер делает воздух прохладнее" in text
    assert "заметно влияет на комфорт" in text
    assert "маршрут под крышей" not in text.lower()

