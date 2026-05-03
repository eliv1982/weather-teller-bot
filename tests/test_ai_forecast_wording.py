from ai import fallbacks, prompts


def test_forecast_day_prompt_blocks_awkward_phrases_and_uses_mmhg_pressure_guidance():
    prompt = prompts.build_forecast_day_prompt(
        "Москва",
        [{"main": {"pressure": 1013}, "weather": [{"description": "ясно"}]}],
    )

    assert "без лишней суеты" not in prompt
    assert "без особых акцентов" not in prompt
    assert "без драматизации" not in prompt
    assert "мм рт. ст." in prompt
    assert "Давление в пределах нормы." in prompt


def test_tomorrow_forecast_prompt_is_not_recommendation_style():
    prompt = prompts.build_tomorrow_forecast_prompt(
        "Москва",
        [
            {"main": {"pressure": 1010}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}},
            {"main": {"pressure": 1012}, "weather": [{"description": "ясно"}], "wind": {"speed": 4}},
        ],
    )

    assert "Рекомендация на день" not in prompt
    assert "лучшее окно для прогулки" not in prompt
    assert "без драматизации" not in prompt
    assert "без лишней суеты" not in prompt
    assert "без особых акцентов" not in prompt
    assert "мм рт. ст." in prompt
    assert "hPa" not in prompt
    assert "гПа" not in prompt
    assert "1010" not in prompt
    assert "1012" not in prompt
    assert "Давление: 758 мм рт. ст., в пределах нормы." in prompt
    assert "main" not in prompt
    assert "pressure_note" not in prompt
    assert "слабый до заметного" not in prompt
    assert "слабый до умеренного" not in prompt
    assert "Дождя не видно" not in prompt
    assert "Дождь не ожидается." in prompt
    assert "Существенных осадков не ожидается." in prompt


def test_tomorrow_forecast_prompt_does_not_relabel_raw_pressure_as_mmhg():
    prompt = prompts.build_tomorrow_forecast_prompt(
        "Москва",
        [
            {"main": {"pressure": 1009, "temp": 10}, "weather": [{"description": "ясно"}]},
            {"main": {"pressure": 1012, "temp": 12}, "weather": [{"description": "ясно"}]},
        ],
    )

    assert "1009" not in prompt
    assert "1012" not in prompt
    assert "1009-1012 мм рт. ст." not in prompt
    assert "1009–1012 мм рт. ст." not in prompt
    assert "Давление: 758 мм рт. ст., в пределах нормы." in prompt
    assert "hPa" not in prompt
    assert "гПа" not in prompt
    assert "Сводка прогноза на завтра" in prompt
    assert "Слоты прогноза на завтра" not in prompt


def test_forecast_day_fallback_uses_normal_pressure_wording_in_mmhg():
    text = fallbacks.fallback_day_forecast(
        "Москва",
        [
            {
                "dt_txt": "2026-05-03 12:00:00",
                "main": {"temp": 15, "pressure": 1013},
                "weather": [{"description": "ясно"}],
            }
        ],
    )

    assert "Давление в пределах нормы." in text
    assert "hPa" not in text
    assert "без лишней суеты" not in text
    assert "без особых акцентов" not in text
    assert "без драматизации" not in text


def test_forecast_day_fallback_uses_mmhg_for_clear_pressure():
    low_text = fallbacks.fallback_day_forecast(
        "Москва",
        [
            {
                "dt_txt": "2026-05-03 12:00:00",
                "main": {"temp": 15, "pressure": 1000},
                "weather": [{"description": "ясно"}],
            }
        ],
    )

    assert "750 мм рт. ст." in low_text
    assert "hPa" not in low_text


def test_tomorrow_forecast_fallback_uses_explanation_style_and_pressure_mmhg():
    text = fallbacks.fallback_tomorrow_forecast(
        "Москва",
        [
            {
                "dt_txt": "2026-05-03 09:00:00",
                "main": {"temp": 10, "feels_like": 8, "pressure": 1013},
                "wind": {"speed": 4},
                "weather": [{"description": "ясно"}],
            },
            {
                "dt_txt": "2026-05-03 12:00:00",
                "main": {"temp": 15, "feels_like": 14, "pressure": 1013},
                "wind": {"speed": 5},
                "weather": [{"description": "ясно"}],
            },
        ],
    )

    assert text.startswith("Завтра в Москва")
    assert "Рекомендация на день" not in text
    assert "лучшее окно для прогулки" not in text
    assert "Дождя не видно" not in text
    assert "слабый до заметного" not in text
    assert "слабый до умеренного" not in text
    assert "без драматизации" not in text
    assert "без лишней суеты" not in text
    assert "без особых акцентов" not in text
    assert "Давление: 760 мм рт. ст., в пределах нормы." in text
    assert "Существенных осадков не ожидается." in text
    assert "Ветер умеренный." in text
    assert "hPa" not in text
    assert "гПа" not in text


def test_tomorrow_forecast_fallback_does_not_relabel_raw_pressure_as_mmhg():
    text = fallbacks.fallback_tomorrow_forecast(
        "Москва",
        [
            {
                "dt_txt": "2026-05-03 09:00:00",
                "main": {"temp": 10, "feels_like": 8, "pressure": 1009},
                "wind": {"speed": 4},
                "weather": [{"description": "ясно"}],
            },
            {
                "dt_txt": "2026-05-03 12:00:00",
                "main": {"temp": 12, "feels_like": 10, "pressure": 1012},
                "wind": {"speed": 4},
                "weather": [{"description": "ясно"}],
            },
        ],
    )

    assert "1009" not in text
    assert "1012" not in text
    assert "1009-1012 мм рт. ст." not in text
    assert "1009–1012 мм рт. ст." not in text
    assert "Давление: 758 мм рт. ст., в пределах нормы." in text
    assert "hPa" not in text
    assert "гПа" not in text


def test_tomorrow_forecast_fallback_uses_clear_wind_and_soft_low_pressure():
    text = fallbacks.fallback_tomorrow_forecast(
        "Москва",
        [
            {
                "dt_txt": "2026-05-03 09:00:00",
                "main": {"temp": 10, "feels_like": 8, "pressure": 990},
                "wind": {"speed": 2},
                "weather": [{"description": "небольшой дождь"}],
            },
            {
                "dt_txt": "2026-05-03 12:00:00",
                "main": {"temp": 15, "feels_like": 14, "pressure": 994},
                "wind": {"speed": 6},
                "weather": [{"description": "небольшой дождь"}],
            },
        ],
    )

    assert "Возможны осадки." in text
    assert "Ветер заметный, но не сильный." in text
    assert "Давление: 743-746 мм рт. ст., ниже обычного." in text
    assert "слабый до заметного" not in text
    assert "hPa" not in text
    assert "гПа" not in text
