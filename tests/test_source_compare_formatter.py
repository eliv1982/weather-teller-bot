from formatters import format_source_compare_response


def _payload(min_temp, max_temp, desc, precip, wind, **extra):
    payload = {
        "min_temp": min_temp,
        "max_temp": max_temp,
        "dominant_description": desc,
        "precipitation_text": precip,
        "wind_text": wind,
        "wind_signal": {"min_speed": 0.0, "avg_speed": 0.0, "max_speed": 0.0},
        "precipitation_signal": {},
    }
    payload.update(extra)
    return payload


def test_formatter_source_blocks_include_numeric_fields_when_available():
    text = format_source_compare_response(
        "Москва",
        _payload(
            7,
            14,
            "небольшой дождь",
            "высокий шанс дождя",
            "умеренный",
            min_feels_like=5,
            max_feels_like=12,
            min_humidity=60,
            max_humidity=78,
            min_pressure=1007,
            max_pressure=1012,
            wind_signal={"min_speed": 3.8, "avg_speed": 5.0, "max_speed": 6.4},
            precipitation_signal={"max_pop": 0.9, "max_amount": 1.2},
        ),
        _payload(
            7,
            11,
            "пасмурно",
            "возможны осадки",
            "слабый",
            min_humidity=58,
            max_humidity=74,
            min_pressure=1008,
            max_pressure=1011,
            wind_signal={"min_speed": 1.8, "avg_speed": 2.7, "max_speed": 3.5},
            precipitation_signal={"max_pop": 0.5},
        ),
    )

    assert "• ощущается как: 5-12 °C" in text
    assert "• вероятность осадков: до 90%" in text
    assert "• количество осадков: до 1.2 мм" in text
    assert "• ветер: 3.8-6.4 м/с, умеренный" in text
    assert "• ветер: 1.8-3.5 м/с, слабый" in text
    assert "• влажность: 60-78%" in text
    assert "• давление: 755-759 мм рт. ст." in text


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
    assert "По ветру прогнозы близки: оба источника показывают умеренный ветер." in text
    assert "Кратко:" not in text


def test_formatter_sources_differ_on_precipitation():
    text = format_source_compare_response(
        "Москва",
        _payload(
            7,
            14,
            "переменная облачность",
            "высокий шанс дождя",
            "умеренный",
            wind_signal={"min_speed": 3.8, "avg_speed": 5.0, "max_speed": 6.4},
        ),
        _payload(
            7,
            11,
            "переменная облачность",
            "возможны осадки",
            "слабый",
            wind_signal={"min_speed": 1.8, "avg_speed": 2.7, "max_speed": 3.5},
        ),
    )
    assert "Источники расходятся по осадкам" in text
    assert "OpenWeather показывает высокий шанс дождя" in text
    assert "По температуре есть умеренное расхождение: OpenWeather даёт 7-14 °C, Open-Meteo — 7-11 °C." in text
    assert "По ветру прогнозы различаются: OpenWeather даёт 3.8-6.4 м/с, умеренный, Open-Meteo — 1.8-3.5 м/с, слабый." in text
    assert "прогнозы температура" not in text
    assert "Open-Meteo мягче" not in text
    assert "более слабый ветер:" not in text
    assert "слабый против слабый" not in text


def test_formatter_treats_close_same_category_wind_as_small_difference():
    text = format_source_compare_response(
        "Москва",
        _payload(
            7,
            14,
            "облачно",
            "без существенных осадков",
            "слабый",
            wind_signal={"min_speed": 1.5, "avg_speed": 2.2, "max_speed": 3.0},
        ),
        _payload(
            7,
            13,
            "облачно",
            "без существенных осадков",
            "слабый",
            wind_signal={"min_speed": 1.3, "avg_speed": 1.6, "max_speed": 1.9},
        ),
    )

    assert "По ветру различия небольшие: OpenWeather даёт 1.5-3.0 м/с, слабый, Open-Meteo — 1.3-1.9 м/с, слабый." in text
    assert "По ветру прогнозы различаются" not in text
    assert "Open-Meteo мягче" not in text
    assert "слабый против слабый" not in text


def test_formatter_treats_overlapping_neighbor_categories_as_small_disagreement():
    text = format_source_compare_response(
        "Москва",
        _payload(
            7,
            14,
            "облачно",
            "без существенных осадков",
            "умеренный",
            wind_signal={"min_speed": 2.5, "avg_speed": 3.4, "max_speed": 4.1},
        ),
        _payload(
            7,
            13,
            "облачно",
            "без существенных осадков",
            "слабый",
            wind_signal={"min_speed": 2.1, "avg_speed": 2.8, "max_speed": 3.8},
        ),
    )

    assert "По ветру есть небольшое расхождение: OpenWeather даёт 2.5-4.1 м/с, умеренный, Open-Meteo — 2.1-3.8 м/с, слабый." in text
    assert "По ветру прогнозы различаются" not in text


def test_formatter_marks_noticeable_temperature_difference():
    text = format_source_compare_response(
        "Москва",
        _payload(4, 18, "облачно", "без существенных осадков", "умеренный"),
        _payload(11, 25, "облачно", "без существенных осадков", "умеренный"),
    )
    assert "По температуре есть заметное расхождение: OpenWeather даёт 4-18 °C, Open-Meteo — 11-25 °C." in text
