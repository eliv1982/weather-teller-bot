from copy import deepcopy

from ai import prompts


RAW_DESCRIPTION = "небольшой проливной дождь"
NORMALIZED_DESCRIPTION = "небольшой кратковременный дождь"


def test_build_current_prompt_normalizes_description_without_mutating_input():
    weather_data = {
        "main": {"temp": 10, "feels_like": 8},
        "weather": [{"description": RAW_DESCRIPTION}],
        "wind": {"speed": 4},
    }
    original = deepcopy(weather_data)

    prompt = prompts.build_current_prompt("Москва", weather_data)

    assert NORMALIZED_DESCRIPTION in prompt
    assert RAW_DESCRIPTION not in prompt
    assert "нужен ли зонт" not in prompt
    assert "есть ли сейчас осадки" in prompt
    assert "Осадки упоминай один раз." in prompt
    assert "идут осадки" in prompt
    assert weather_data == original


def test_build_history_prompt_normalizes_description_and_sets_no_advice_rules():
    history_data = {
        "date": "2026-05-01",
        "temperature_max": 8.0,
        "temperature_min": 2.0,
        "temperature_mean": 5.0,
        "wind_speed_max": 4.0,
        "weather_description": RAW_DESCRIPTION,
    }
    original = deepcopy(history_data)

    prompt = prompts.build_history_prompt("Москва", history_data)

    assert NORMALIZED_DESCRIPTION in prompt
    assert RAW_DESCRIPTION not in prompt
    assert "Не давай рекомендаций." in prompt
    assert "Не сравнивай с другими днями." in prompt
    assert "Пиши через обычную е." in prompt
    assert history_data == original


def test_build_history_prompt_formats_pressure_for_user_facing_units():
    history_data = {
        "date": "2026-05-01",
        "temperature_max": 8.0,
        "temperature_min": 2.0,
        "temperature_mean": 5.0,
        "pressure_mean": 1020.2,
        "weather_description": "пасмурно",
    }

    prompt = prompts.build_history_prompt("Москва", history_data)

    assert "Давление: 765 мм рт. ст." in prompt
    assert "1020.2" not in prompt
    assert "pressure_mean" not in prompt
    assert "Не пиши hPa, гПа" in prompt


def test_build_details_prompt_normalizes_description_without_mutating_input():
    weather_data = {
        "main": {"temp": 10, "feels_like": 8, "humidity": 70},
        "weather": [{"description": RAW_DESCRIPTION}],
        "wind": {"speed": 4},
        "visibility": 10000,
    }
    original = deepcopy(weather_data)

    prompt = prompts.build_details_prompt("Москва", weather_data, {"pm2_5": 12})

    assert NORMALIZED_DESCRIPTION in prompt
    assert RAW_DESCRIPTION not in prompt
    assert weather_data == original


def test_build_forecast_day_prompt_normalizes_each_slot_without_mutating_input():
    day_forecast_data = [
        {
            "dt_txt": "2026-05-02 09:00:00",
            "main": {"temp": 9},
            "weather": [{"description": RAW_DESCRIPTION}],
        },
        {
            "dt_txt": "2026-05-02 12:00:00",
            "main": {"temp": 11},
            "weather": [{"description": "небольшой ливневый дождь"}],
        },
    ]
    original = deepcopy(day_forecast_data)

    prompt = prompts.build_forecast_day_prompt("Москва", day_forecast_data)

    assert prompt.count(NORMALIZED_DESCRIPTION) == 2
    assert RAW_DESCRIPTION not in prompt
    assert "небольшой ливневый дождь" not in prompt
    assert day_forecast_data == original


def test_build_weather_alert_prompt_normalizes_description_without_mutating_input():
    alert_payload = {
        "slot_local": "02.05 18:00",
        "description": RAW_DESCRIPTION,
        "temperature": 10,
        "wind_speed": 4,
    }
    original = deepcopy(alert_payload)

    prompt = prompts.build_weather_alert_prompt("Москва", alert_payload)

    assert NORMALIZED_DESCRIPTION in prompt
    assert RAW_DESCRIPTION not in prompt
    assert alert_payload == original


def test_weather_alert_prompt_does_not_encourage_time_based_generic_advice():
    prompt = prompts.build_weather_alert_prompt("Москва", {"description": "пасмурно"})

    assert "выйти чуть раньше" not in prompt
    assert "время выхода" not in prompt
    assert "менее открытые места" not in prompt
    assert "время посуше" not in prompt
    assert "время по суше" not in prompt
