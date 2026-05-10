from formatters import format_source_compare_response


def _payload(min_temp, max_temp, desc, precip, wind):
    return {
        "min_temp": min_temp,
        "max_temp": max_temp,
        "dominant_description": desc,
        "precipitation_text": precip,
        "wind_text": wind,
    }


def test_formatter_sources_agree_on_precipitation_and_temperature_close():
    text = format_source_compare_response(
        "Москва",
        _payload(10, 22, "переменная облачность", "без существенных осадков", "умеренный"),
        _payload(9, 21, "переменная облачность", "без существенных осадков", "умеренный"),
    )
    assert "🔎 Сравнение прогнозов на завтра" in text
    assert "• осадки: не ожидаются" in text
    assert "✨ Источники в целом сходятся" in text
    assert "температура близкая" in text
    assert "Кратко:" not in text


def test_formatter_sources_differ_on_precipitation():
    text = format_source_compare_response(
        "Москва",
        _payload(10, 22, "переменная облачность", "возможен дождь", "умеренный"),
        _payload(9, 21, "переменная облачность", "без существенных осадков", "умеренный"),
    )
    assert "Источники расходятся по осадкам" in text
    assert "OpenWeather показывает возможен дождь" in text


def test_formatter_marks_noticeable_temperature_difference():
    text = format_source_compare_response(
        "Москва",
        _payload(4, 18, "облачно", "без существенных осадков", "умеренный"),
        _payload(11, 25, "облачно", "без существенных осадков", "умеренный"),
    )
    assert "температура заметно отличается" in text
