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
    return [line for line in text.splitlines() if line.startswith("✨ ")]


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
    assert text.count("✨ ") == 2
    assert "Кратко:" not in text
    assert "Воздух сухой" in text
    assert "Влажность умеренная" in text
    assert "В локации Тольятти: прохладно и пасмурно, ощущается около 6 °C." in text
    assert "В локации Санкт-Петербург: тепло и ясно, ощущается около 17 °C." in text
    assert "В Тольятти" not in text
    assert "\n✨ Москва:" not in text
    assert "ветер умеренный, осадков по текущим данным нет." in text.lower()
    assert "ветер слабый, осадков по текущим данным нет." in text.lower()
    for comment in _short_comments(text):
        assert comment[2:3].isupper()
        assert ". " in comment
        assert "в Москва" not in comment
        assert "в Санкт-Петербург" not in comment
        assert "В локации " in comment
        assert "Лучше" not in comment
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
    assert "идут осадки" not in text.lower()
    assert "идёт снег" in text.lower()
    assert "В локации Екатеринбург: прохладно, идёт дождь, ощущается около 2 °C." in text
    assert "В локации Москва: холодно, идёт снег, ощущается около -5 °C." in text
    assert "влажно, ветер заметный." in text.lower()
    assert "влажность умеренная, ветер сильный." in text.lower()
    assert text.count("✨ ") == 2
    assert "Кратко:" not in text
    for comment in _short_comments(text):
        assert comment[2:3].isupper()
        assert ". " in comment
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
    assert "ожидается небольшой дождь" in text
    assert "без осадков" in text
    assert text.count("✨ ") == 2
    assert "Кратко:" not in text
    assert "В локации Тольятти: ожидается прохладная погода, температура около 5.0°C-12.0°C. Ожидается небольшой дождь, вероятность до 45%. Ветер умеренный." in text
    assert "В локации Санкт-Петербург: ожидается тёплая облачная погода, температура около 14.0°C-21.0°C. Без осадков. Ветер слабый." in text
    assert "В Тольятти" not in text
    assert "\n✨ Тольятти:" not in text
    assert "идут осадки" not in text
    for comment in _short_comments(text):
        assert comment[2:3].isupper()
        assert ". " in comment
        assert "в Санкт-Петербург" not in comment
        assert "В локации " in comment
        assert "будет небольшой дождь" not in comment
    _assert_no_advisory_or_comparative_phrases(text)


def test_forecast_summary_prefers_specific_precipitation_type_over_generic(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    text = service.compare_two_locations_forecast_day_with_ai(
        _forecast_payload(
            "Москва",
            min_temp=7,
            max_temp=15,
            description="дождь",
            max_pop=0.3,
            avg_wind=3,
            max_wind=5,
        ),
        _forecast_payload(
            "Тула",
            min_temp=8,
            max_temp=14,
            description="пасмурно",
            max_pop=0.0,
            avg_wind=2,
            max_wind=4,
        ),
        "05.05",
    )

    assert "возможен дождь" in text
    assert "возможны осадки" not in text


def test_history_fallback_stays_factual_and_has_no_yo(monkeypatch):
    AiWeatherService = _import_service_with_stubbed_postgres(monkeypatch)
    service = AiWeatherService(api_key="")

    text = service.explain_history_weather(
        "Тольятти",
        {
            "date": "2026-05-01",
            "date_label": "01.05.2026",
            "temperature_max": 2.0,
            "temperature_min": -1.0,
            "temperature_mean": 0.0,
            "precipitation_sum": 0.0,
            "rain_sum": 0.0,
            "snowfall_sum": 0.0,
            "wind_speed_max": 4.0,
            "relative_humidity_mean": 93.0,
            "pressure_mean": 1025.0,
            "weather_description": "пасмурно",
        },
    )

    lowered = text.lower()
    assert "по архивным данным" in lowered
    assert "лучше" not in lowered
    assert "одеться" not in lowered
    assert "совет" not in lowered
    assert "\u0451" not in lowered
