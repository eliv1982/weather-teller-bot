from ai import fallbacks, prompts
from formatters import format_details_response, format_weather_response
from weather.pressure import HIGH_PRESSURE_NOTE, LOW_PRESSURE_NOTE, get_pressure_note_hpa


def _weather_with_pressure(pressure: object) -> dict:
    return {
        "main": {
            "temp": 12,
            "feels_like": 10,
            "humidity": 60,
            "pressure": pressure,
        },
        "weather": [{"description": "пасмурно"}],
        "wind": {"speed": 3, "deg": 180},
        "visibility": 10000,
    }


def test_pressure_helper_returns_low_note_at_threshold():
    assert get_pressure_note_hpa(1000) == LOW_PRESSURE_NOTE


def test_pressure_helper_returns_high_note_at_threshold():
    assert get_pressure_note_hpa(1025) == HIGH_PRESSURE_NOTE


def test_pressure_helper_returns_none_for_normal_pressure():
    assert get_pressure_note_hpa(1013) is None


def test_pressure_helper_returns_none_for_missing_or_non_numeric_values():
    assert get_pressure_note_hpa(None) is None
    assert get_pressure_note_hpa("1000") is None


def test_format_weather_response_includes_low_and_high_pressure_notes():
    low_text = format_weather_response("Москва", _weather_with_pressure(1000))
    high_text = format_weather_response("Москва", _weather_with_pressure(1025))

    assert LOW_PRESSURE_NOTE in low_text
    assert HIGH_PRESSURE_NOTE in high_text
    assert "🩺 Давление:" in low_text
    assert "🩺 Давление:" in high_text


def test_format_details_response_includes_low_and_high_pressure_notes():
    low_text = format_details_response("Москва", _weather_with_pressure(1000), None)
    high_text = format_details_response("Москва", _weather_with_pressure(1025), None)

    assert LOW_PRESSURE_NOTE in low_text
    assert HIGH_PRESSURE_NOTE in high_text
    assert "🩺 Давление:" in low_text
    assert "🩺 Давление:" in high_text


def test_formatters_do_not_add_pressure_note_for_normal_pressure():
    current_text = format_weather_response("Москва", _weather_with_pressure(1013))
    details_text = format_details_response("Москва", _weather_with_pressure(1013), None)

    assert LOW_PRESSURE_NOTE not in current_text
    assert HIGH_PRESSURE_NOTE not in current_text
    assert LOW_PRESSURE_NOTE not in details_text
    assert HIGH_PRESSURE_NOTE not in details_text


def test_current_fallback_adds_pressure_note_only_for_clear_pressure():
    low_text = fallbacks.fallback_current("Москва", _weather_with_pressure(1000))
    normal_text = fallbacks.fallback_current("Москва", _weather_with_pressure(1013))

    assert LOW_PRESSURE_NOTE in low_text
    assert LOW_PRESSURE_NOTE not in normal_text
    assert HIGH_PRESSURE_NOTE not in normal_text
    assert "По ощущениям погода без явного дискомфорта." not in low_text
    assert "На улице в целом довольно комфортно." not in low_text


def test_current_fallback_keeps_comfort_phrase_without_caution_factors():
    weather = _weather_with_pressure(1013)
    weather["main"]["temp"] = 20
    weather["main"]["feels_like"] = 20
    weather["wind"]["speed"] = 2

    text = fallbacks.fallback_current("Москва", weather)

    assert LOW_PRESSURE_NOTE not in text
    assert HIGH_PRESSURE_NOTE not in text
    assert "По ощущениям погода без явного дискомфорта." in text


def test_current_fallback_uses_precipitation_wording_without_umbrella_advice():
    weather = _weather_with_pressure(1013)

    text = fallbacks.fallback_current("Москва", weather)

    assert "Зонт не нужен" not in text
    assert "можно обойтись без зонта" not in text
    assert "По текущим данным, осадков сейчас нет." in text


def test_details_fallback_adds_pressure_note_only_for_clear_pressure():
    high_text = fallbacks.fallback_details("Москва", _weather_with_pressure(1025), {"pm2_5": 12})
    normal_text = fallbacks.fallback_details("Москва", _weather_with_pressure(1013), {"pm2_5": 12})

    assert HIGH_PRESSURE_NOTE in high_text
    assert LOW_PRESSURE_NOTE not in normal_text
    assert HIGH_PRESSURE_NOTE not in normal_text


def test_current_and_details_prompts_include_soft_pressure_guidance():
    current_prompt = prompts.build_current_prompt("Москва", _weather_with_pressure(1000))
    details_prompt = prompts.build_details_prompt("Москва", _weather_with_pressure(1025), None)

    for prompt in (current_prompt, details_prompt):
        assert "Давление упоминай только если оно явно низкое" in prompt
        assert "без медицинских утверждений" in prompt
        assert "мягкий фактор" in prompt
