from formatters import (
    build_history_brief_summary,
    build_monthly_climate_brief_summary,
    format_history_monthly_climate_response,
    format_history_weather_response,
)


def _history_payload(**overrides):
    payload = {
        "date": "2026-05-01",
        "date_label": "01.05.2026",
        "temperature_max": 18.4,
        "temperature_min": 9.1,
        "temperature_mean": 13.2,
        "precipitation_sum": 0.0,
        "rain_sum": 0.0,
        "snowfall_sum": 0.0,
        "wind_speed_max": 7.4,
        "wind_direction_dominant": 225.0,
        "relative_humidity_mean": 71.0,
        "pressure_mean": 1012.8,
        "weather_description": "пасмурно",
    }
    payload.update(overrides)
    return payload


def _monthly_year_payload(**overrides):
    payload = {
        "mode": "monthly_year",
        "month": 1,
        "month_label": "Январь",
        "month_label_lower": "январь",
        "year": 2020,
        "temperature_month_mean": -2.0,
        "temperature_daily_max_mean": 1.0,
        "temperature_daily_min_mean": -5.0,
        "temperature_absolute_max": 4.0,
        "temperature_absolute_min": -12.0,
        "warmest_day_label": "14.01.2020",
        "coldest_day_label": "03.01.2020",
        "precipitation_month_sum": 35.0,
        "rain_month_sum": 20.0,
        "snowfall_month_sum": 15.0,
        "precipitation_days": 11,
        "precipitation_days_share": 0.35,
        "wind_daily_max_mean": 5.2,
        "wind_month_peak": 11.4,
        "windiest_day_label": "22.01.2020",
        "relative_humidity_mean": 78.0,
        "pressure_mean": 1012.0,
        "dominant_weather_description": "пасмурно",
    }
    payload.update(overrides)
    return payload


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


def test_history_formatter_marks_rain_when_rain_sum_present():
    text = format_history_weather_response(
        "Москва",
        _history_payload(
            precipitation_sum=5.4,
            rain_sum=5.4,
            weather_description="дождь",
        ),
    )

    assert "🕰 История погоды: Москва" in text
    assert "📅 01.05.2026" in text
    assert "🌧 Осадки" in text
    assert "• По архивным данным: дождь" in text


def test_history_formatter_marks_snow_when_snowfall_present():
    text = format_history_weather_response(
        "Москва",
        _history_payload(
            precipitation_sum=2.0,
            snowfall_sum=3.5,
            weather_description="снег",
        ),
    )

    assert "• По архивным данным: снег" in text
    assert "• Снег: 3.5 см" in text


def test_history_formatter_marks_no_precipitation_when_sums_are_zero():
    text = format_history_weather_response("Москва", _history_payload())

    assert "• По архивным данным: без существенных осадков" in text


def test_history_formatter_shows_wind_speed_and_direction():
    text = format_history_weather_response("Москва", _history_payload(wind_speed_max=7.4, wind_direction_dominant=225.0))

    assert "💨 Ветер" in text
    assert "• Максимальная скорость: 7.4 м/с" in text
    assert "• Преобладающее направление: юго-западный" in text


def test_history_formatter_uses_emoji_sections_and_short_block():
    text = format_history_weather_response("Москва", _history_payload())

    for label in (
        "🕰 История погоды: Москва",
        "📅 01.05.2026",
        "🌡 Температура",
        "🌧 Осадки",
        "💨 Ветер",
        "📊 Дополнительно",
        "✨ Коротко",
    ):
        assert label in text


def test_history_formatter_falls_back_to_brief_summary_without_ai_text():
    text = format_history_weather_response("Москва", _history_payload(relative_humidity_mean=93.0))

    assert "По архивным данным" in text
    assert "Влажность" in text
    assert "\u0451" not in text


def test_history_formatter_uses_mmhg_in_short_block_and_hides_raw_pressure():
    text = format_history_weather_response("Москва", _history_payload(pressure_mean=1020.2, relative_humidity_mean=93.0))
    short_block = text.split("✨ Коротко", 1)[1]

    assert "765 мм рт. ст." in text
    assert "1020.2" not in short_block
    assert "мм рт. ст." in short_block or "давлен" not in short_block.lower()


def test_history_formatter_normalizes_negative_zero_temperature():
    text = format_history_weather_response(
        "Москва",
        _history_payload(
            temperature_max=-0.0,
            temperature_min=-0.0,
            temperature_mean=-0.0,
        ),
    )

    assert "-0.0 °C" not in text
    assert "• Максимум: 0.0 °C" in text
    assert "• Минимум: 0.0 °C" in text
    assert "• Средняя: 0.0 °C" in text


def test_history_formatter_accepts_external_short_summary():
    text = format_history_weather_response(
        "Москва",
        _history_payload(),
        short_summary="По архивным данным день выглядел спокойно и без существенных осадков.",
    )

    assert "✨ Коротко" in text
    assert "По архивным данным день выглядел спокойно и без существенных осадков." in text


def test_build_history_brief_summary_mentions_archive_and_has_no_yo():
    text = build_history_brief_summary(_history_payload(relative_humidity_mean=93.0, weather_description="пасмурно"))

    assert "По архивным данным" in text
    assert "пасмурно" in text
    assert "\u0451" not in text


def test_build_history_brief_summary_formats_pressure_in_mmhg():
    text = build_history_brief_summary(_history_payload(pressure_mean=1020.2, relative_humidity_mean=60.0))

    assert "765 мм рт. ст." in text
    assert "1020.2" not in text


def test_monthly_year_formatter_uses_emoji_sections_and_short_block():
    text = format_history_monthly_climate_response("Москва", _monthly_year_payload())

    for label in (
        "📊 Средние климатические показатели",
        "📍 Москва",
        "🗓 Январь 2020",
        "🌡 Температура",
        "🌧 Осадки",
        "💨 Ветер",
        "📊 Дополнительно",
        "✨ Коротко",
    ):
        assert label in text


def test_monthly_normals_formatter_mentions_archive_period_without_forecast_wording():
    text = format_history_monthly_climate_response("Москва", _monthly_normals_payload())

    assert "📆 Среднемесячные показатели" in text
    assert "период 1991-2020" in text
    assert "использовано 24 из 30 лет" in text.lower()
    assert "прогноз" not in text.lower()
    assert "вероятность осадков" not in text.lower()
    assert "архив" in text.lower()


def test_monthly_formatter_hides_raw_pressure_and_no_yo():
    text = format_history_monthly_climate_response("Москва", _monthly_normals_payload(pressure_mean=1020.2))

    assert "765 мм рт. ст." in text
    assert "1020.2" not in text
    assert "\u0451" not in text


def test_build_monthly_climate_brief_summary_avoids_probability_wording():
    text = build_monthly_climate_brief_summary(_monthly_normals_payload())

    assert "доля дней с осадками по архивным данным" in text.lower()
    assert "использовано 24 из 30 лет" in text.lower()
    assert "вероятность осадков" not in text.lower()
    assert "прогноз" not in text.lower()
    assert "1991-2020" in text
