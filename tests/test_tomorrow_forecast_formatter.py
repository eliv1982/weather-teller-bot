from formatters import format_tomorrow_forecast_response


def test_format_tomorrow_forecast_response_is_dedicated_card_with_pressure_mmhg():
    text = format_tomorrow_forecast_response(
        "Москва",
        "03.05",
        [
            {
                "dt_txt": "2026-05-03 09:00:00",
                "main": {"temp": 10, "feels_like": 8, "humidity": 70, "pressure": 1013},
                "weather": [{"description": "облачно"}],
                "wind": {"speed": 3, "deg": 90},
            },
            {
                "dt_txt": "2026-05-03 12:00:00",
                "main": {"temp": 15, "feels_like": 14, "humidity": 60, "pressure": 1015},
                "weather": [{"description": "облачно"}],
                "wind": {"speed": 5, "deg": 90},
            },
        ],
    )

    assert text.startswith("🌤 Прогноз на завтра")
    assert "📍 Населённый пункт: Москва" in text
    assert "📅 Дата: 03.05" in text
    assert "🌡 Температура: 10.0...15.0 °C" in text
    assert "🤔 Ощущается как: 8.0...14.0 °C" in text
    assert "☁️ Описание: облачно" in text
    assert "💧 Влажность: 65%" in text
    assert "🩺 Давление: 761 мм рт. ст." in text
    assert "🌬 Ветер: 5.0 м/с, восточный" in text
    assert "🕒 По времени:" not in text


def test_tomorrow_forecast_response_handles_missing_optional_values():
    text = format_tomorrow_forecast_response("Москва", "03.05", [])

    assert "🌡 Температура: н/д" in text
    assert "🤔 Ощущается как: н/д" in text
    assert "💧 Влажность: н/д%" in text
    assert "🩺 Давление: н/д мм рт. ст." in text
    assert "🌬 Ветер: н/д" in text
