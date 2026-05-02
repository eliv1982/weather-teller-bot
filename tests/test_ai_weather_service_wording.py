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


WINNER_STYLE_PHRASES = (
    "лидер",
    "победитель",
    "выигрывает",
    "лучше выглядит",
    "однозначного лидера",
    "для прогулки лучше",
    "для поездки практичнее",
    "практичнее",
)


def _assert_no_winner_style_phrases(text: str):
    lowered = text.lower()
    for phrase in WINNER_STYLE_PHRASES:
        assert phrase not in lowered


def test_compare_current_clear_uses_neutral_tradeoff(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    text = service._render_compare_current_clear(
        1,
        "Екатеринбург",
        "Сочи",
        "Екатеринбург",
        "Сочи",
        warmer=1,
        calmer=1,
        drier=1,
        no_rain=1,
    )

    assert "Екатеринбург" in text
    assert "Сочи" in text
    assert "Если важнее" in text
    _assert_no_winner_style_phrases(text)


def test_compare_current_mixed_uses_priority_tradeoff(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    text = service._render_compare_current_mixed(
        "Екатеринбург",
        "Москва",
        "Екатеринбург",
        "Москва",
        warmer=1,
        calmer=None,
        drier=2,
        no_rain=2,
    )

    assert "Если важнее тепло" in text
    assert "Если важнее сухо" in text
    _assert_no_winner_style_phrases(text)


def test_compare_by_date_near_identical_uses_neutral_location_pair(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    profile_1 = {
        "city_label": "Екатеринбург",
        "temperature_note": "умеренно тепло",
        "precipitation_risk": "low",
        "wind_risk": "low",
    }
    profile_2 = {
        "city_label": "Москва",
        "temperature_note": "умеренно тепло",
        "precipitation_risk": "low",
        "wind_risk": "low",
    }

    text = service._render_compare_forecast_near_identical(
        profile_1,
        profile_2,
        "Екатеринбург",
        "Москва",
        "Екатеринбург",
        "Москва",
    )
    assert "между Екатеринбург и Москва" not in text
    assert "Для локаций «Екатеринбург» и «Москва»" in text
    assert "В Москва" not in text
    assert "Условия близки" in text
    _assert_no_winner_style_phrases(text)


def test_compare_by_date_mixed_does_not_contain_v_moskva(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    profile_1 = {
        "city_label": "Екатеринбург",
        "avg_temp": 10,
        "precipitation_risk": "medium",
        "precipitation_type": "rain",
        "wind_risk": "medium",
    }
    profile_2 = {
        "city_label": "Москва",
        "avg_temp": 12,
        "precipitation_risk": "low",
        "precipitation_type": "none",
        "wind_risk": "low",
    }
    verdict = {"warmer_city": "Москва", "drier_city": "Москва", "calmer_city": "Москва"}

    text = service._render_compare_forecast_mixed(
        profile_1,
        profile_2,
        verdict,
        "Екатеринбург",
        "Москва",
        "Екатеринбург",
        "Москва",
        4.0,
        3.0,
    )
    assert "В Москва" not in text


def test_compare_by_date_clear_uses_neutral_tradeoff(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    profile_1 = {
        "city_label": "Екатеринбург",
        "avg_temp": 12,
        "precipitation_risk": "low",
        "precipitation_type": "none",
        "wind_risk": "low",
    }
    profile_2 = {
        "city_label": "Сочи",
        "avg_temp": 8,
        "precipitation_risk": "medium",
        "precipitation_type": "rain",
        "wind_risk": "medium",
    }
    verdict = {
        "winner": "Екатеринбург",
        "warmer_city": "Екатеринбург",
        "drier_city": "Екатеринбург",
        "calmer_city": "Екатеринбург",
    }

    text = service._render_compare_forecast_clear_winner(
        profile_1,
        profile_2,
        verdict,
        "Екатеринбург",
        "Сочи",
        "Екатеринбург",
        "Сочи",
    )

    assert "Екатеринбург" in text
    assert "Сочи" in text
    assert "Если важнее" in text
    assert "Лучше выглядит" not in text
    _assert_no_winner_style_phrases(text)


def test_compare_by_date_mixed_uses_neutral_priority_wording(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    profile_1 = {
        "city_label": "Екатеринбург",
        "avg_temp": 12,
        "precipitation_risk": "medium",
        "precipitation_type": "rain",
        "wind_risk": "medium",
    }
    profile_2 = {
        "city_label": "Москва",
        "avg_temp": 10,
        "precipitation_risk": "low",
        "precipitation_type": "none",
        "wind_risk": "low",
    }
    verdict = {"warmer_city": "Екатеринбург", "drier_city": "Москва", "calmer_city": "Москва"}

    text = service._render_compare_forecast_mixed(
        profile_1,
        profile_2,
        verdict,
        "Екатеринбург",
        "Москва",
        "Екатеринбург",
        "Москва",
        4.0,
        3.0,
    )

    assert "Если важнее тепло" in text
    assert "Если важнее" in text
    assert "Для прогулки лучше" not in text
    _assert_no_winner_style_phrases(text)

