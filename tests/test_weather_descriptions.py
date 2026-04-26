from formatters import format_weather_response
from weather.descriptions import normalize_weather_description


def test_normalize_weather_description_small_torrential():
    assert (
        normalize_weather_description("небольшой проливной дождь")
        == "небольшой кратковременный дождь"
    )


def test_normalize_weather_description_small_shower():
    assert (
        normalize_weather_description("небольшой ливневый дождь")
        == "небольшой кратковременный дождь"
    )


def test_normalize_weather_description_keeps_regular_text():
    assert normalize_weather_description("пасмурно") == "пасмурно"


def test_normalize_weather_description_empty_string():
    assert normalize_weather_description("") == ""


def test_normalize_weather_description_none():
    assert normalize_weather_description(None) == ""


def test_formatter_uses_normalized_description():
    text = format_weather_response(
        "Москва",
        {
            "main": {"temp": 10, "feels_like": 9, "humidity": 60, "pressure": 1010},
            "weather": [{"description": "небольшой проливной дождь"}],
            "wind": {"speed": 3, "deg": 180},
        },
    )
    assert "небольшой кратковременный дождь" in text
    assert "небольшой проливной дождь" not in text

