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


BANNED_COMPARE_PHRASES = (
    "теплее",
    "прохладнее",
    "холоднее",
    "жарче",
    "суше",
    "влажнее",
    "слабее",
    "сильнее",
    "лучше",
    "хуже",
    "практичнее",
    "удобнее",
    "спокойнее",
    "если важнее",
    "у вариантов разные плюсы",
    "условия близки",
    "ориентируйся",
    "выбирай",
    "маршрут",
    "прогулки",
    "поездки",
)


def _assert_no_advisory_or_comparative_phrases(text: str):
    lowered = text.lower()
    for phrase in BANNED_COMPARE_PHRASES:
        assert phrase not in lowered


def _short_comments(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("Кратко:")]


def _current_payload(city_label: str, *, temp: float, feels_like: float, humidity: int, wind: float, description: str):
    return {
        "city_label": city_label,
        "temperature": temp,
        "feels_like": feels_like,
        "description": description,
        "humidity": humidity,
        "wind_speed": wind,
    }


def _forecast_payload(
    city_label: str,
    *,
    min_temp: float,
    max_temp: float,
    description: str,
    max_pop: float,
    avg_wind: float,
    max_wind: float,
):
    return {
        "city_label": city_label,
        "selected_day": "05.05",
        "min_temp": min_temp,
        "max_temp": max_temp,
        "dominant_description": description,
        "precipitation_signal": {"rain_slots": 2, "max_pop": max_pop},
        "wind_signal": {"avg_speed": avg_wind, "max_speed": max_wind},
        "key_day_intervals": ["09:00", "12:00", "15:00"],
    }


def test_compare_current_outputs_factual_blocks(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    text = service.compare_two_locations_current_with_ai(
        _current_payload(
            "Тольятти (Россия, Самарская область)",
            temp=8,
            feels_like=6,
            humidity=35,
            wind=4,
            description="пасмурно",
        ),
        _current_payload(
            "Санкт-Петербург (Россия)",
            temp=18,
            feels_like=17,
            humidity=60,
            wind=2,
            description="ясно",
        ),
    )

    assert "Тольятти" in text
    assert "Санкт-Петербург" in text
    assert text.count("📍") == 2
    for label in ("🌡 Температура", "🤔 Ощущается как", "☁️ Описание", "💧 Влажность", "🌬 Ветер"):
        assert label in text
    assert text.count("Кратко:") == 2
    assert "воздух сухой" in text
    assert "влажность умеренная" in text
    assert "ветер умеренный" in text
    assert "ветер слабый" in text
    for comment in _short_comments(text):
        assert "Тольятти" not in comment
        assert "Санкт-Петербург" not in comment
        assert "в Москва" not in comment
        assert "в Санкт-Петербург" not in comment
    _assert_no_advisory_or_comparative_phrases(text)


def test_compare_current_rain_uses_absolute_precipitation(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    text = service.compare_two_locations_current_with_ai(
        _current_payload("Екатеринбург", temp=4, feels_like=2, humidity=75, wind=7, description="дождь"),
        _current_payload("Москва", temp=-2, feels_like=-5, humidity=50, wind=10, description="снег"),
    )

    assert "Екатеринбург" in text
    assert "Москва" in text
    assert "идёт дождь" in text.lower()
    assert "возможен снег" in text.lower()
    assert "ветер заметный" in text
    assert "ветер сильный" in text
    assert text.count("Кратко:") == 2
    for comment in _short_comments(text):
        assert "Екатеринбург" not in comment
        assert "Москва" not in comment
        assert "в Москва" not in comment
    _assert_no_advisory_or_comparative_phrases(text)


def test_compare_forecast_outputs_factual_blocks(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    text = service.compare_two_locations_forecast_day_with_ai(
        _forecast_payload(
            "Тольятти",
            min_temp=5,
            max_temp=12,
            description="небольшой дождь",
            max_pop=0.45,
            avg_wind=4,
            max_wind=7,
        ),
        _forecast_payload(
            "Санкт-Петербург",
            min_temp=14,
            max_temp=21,
            description="облачно",
            max_pop=0.1,
            avg_wind=2,
            max_wind=4,
        ),
        "05.05",
    )

    assert "Тольятти" in text
    assert "Санкт-Петербург" in text
    assert text.count("📍") == 2
    for label in (
        "📅 Дата",
        "🌡 Температура",
        "🌡 Средняя температура",
        "☁️ Описание",
        "🌧 Осадки",
        "☔ Вероятность осадков",
        "🌬 Ветер",
    ):
        assert label in text
    assert "возможен дождь" in text
    assert "без осадков" in text
    assert text.count("Кратко:") == 2
    for comment in _short_comments(text):
        assert "Тольятти" not in comment
        assert "Санкт-Петербург" not in comment
        assert "в Санкт-Петербург" not in comment
    _assert_no_advisory_or_comparative_phrases(text)


def test_compare_forecast_legacy_renderers_are_factual(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")
    profile_1 = service._build_forecast_day_risk_profile(
        _forecast_payload("Екатеринбург", min_temp=5, max_temp=12, description="дождь", max_pop=0.6, avg_wind=5, max_wind=8)
    )
    profile_2 = service._build_forecast_day_risk_profile(
        _forecast_payload("Москва", min_temp=10, max_temp=18, description="ясно", max_pop=0.0, avg_wind=2, max_wind=3)
    )
    verdict = service._build_forecast_compare_verdict(profile_1, profile_2)

    outputs = [
        service._render_compare_forecast_clear_winner(profile_1, profile_2, verdict, "Екатеринбург", "Москва", "Екатеринбург", "Москва"),
        service._render_compare_forecast_near_identical(profile_1, profile_2, "Екатеринбург", "Москва", "Екатеринбург", "Москва"),
        service._render_compare_forecast_mixed(profile_1, profile_2, verdict, "Екатеринбург", "Москва", "Екатеринбург", "Москва", 4.0, 3.0),
    ]

    for text in outputs:
        assert "Екатеринбург" in text
        assert "Москва" in text
        assert text.count("Кратко:") == 2
        _assert_no_advisory_or_comparative_phrases(text)
