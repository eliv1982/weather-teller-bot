from ai import signatures


def test_build_cache_key_stable_for_equivalent_input():
    signature = {"x": 1, "y": {"z": 2}}
    key_1 = signatures.build_cache_key("model-a", "scenario-a", signature)
    key_2 = signatures.build_cache_key("model-a", "scenario-a", {"y": {"z": 2}, "x": 1})
    assert key_1 == key_2


def test_current_signature_normal_weather_data():
    data = {
        "main": {"temp": 12.2, "feels_like": 10.9, "humidity": 71, "pressure": 1005},
        "wind": {"speed": 4.2},
        "weather": [{"description": "пасмурно"}],
    }
    result = signatures.current_signature("Москва", data)
    assert result["location"] == "москва"
    assert result["description"] == "пасмурно"


def test_current_signature_handles_empty_weather_list():
    data = {"main": {"temp": 15}, "wind": {"speed": 2.0}, "weather": []}
    result = signatures.current_signature("City", data)
    assert isinstance(result, dict)
    assert result["description"] == ""


def test_forecast_signature_handles_empty_weather_list():
    payload = [{"dt_txt": "2026-01-01 12:00:00", "main": {"temp": 1}, "weather": []}]
    result = signatures.forecast_signature("City", payload)
    assert isinstance(result, dict)
    assert result["slots"][0]["description"] is None


def test_details_signature_handles_empty_weather_list():
    data = {"main": {"temp": 5}, "wind": {"speed": 1.2}, "weather": []}
    result = signatures.details_signature("City", data, None)
    assert isinstance(result, dict)
    assert result["description"] is None


def test_compare_current_signature_has_both_location_blocks():
    p1 = {"city_label": "A", "temperature": 1}
    p2 = {"city_label": "B", "temperature": 2}
    result = signatures.compare_current_signature(p1, p2)
    assert "location_1" in result
    assert "location_2" in result
    assert isinstance(result["location_1"], dict)
    assert isinstance(result["location_2"], dict)


def test_tomorrow_forecast_signature_has_prompt_cache_version():
    payload = [
        {
            "dt_txt": "2026-05-04 12:00:00",
            "main": {"temp": 12, "feels_like": 10, "pressure": 1012},
            "wind": {"speed": 4},
            "weather": [{"description": "ясно"}],
        }
    ]

    result = signatures.tomorrow_forecast_signature("Москва", payload)

    assert result["mode"] == "tomorrow_forecast"
    assert result["format_version"] == "tomorrow_ai_v2"


def test_monthly_climate_signature_preserves_mode_specific_cache_version():
    normals = signatures.monthly_climate_signature(
        "Москва",
        {
            "mode": "monthly_normals",
            "month": 1,
            "reference_period": "1991-2020",
            "temperature_month_mean": -3.0,
            "precipitation_month_sum": 42.0,
            "precipitation_days_share_mean": 0.40,
            "dominant_weather_description": "пасмурно",
        },
    )
    yearly = signatures.monthly_climate_signature(
        "Москва",
        {
            "mode": "monthly_year",
            "month": 1,
            "year": 2020,
            "temperature_month_mean": -2.0,
            "precipitation_month_sum": 35.0,
            "precipitation_days_share": 0.35,
            "dominant_weather_description": "пасмурно",
        },
    )

    assert normals["mode"] == "monthly_normals"
    assert normals["format_version"] == "monthly_climate_ai_v1"
    assert yearly["mode"] == "monthly_year"
    assert yearly["format_version"] == "monthly_climate_ai_v1"


def test_weather_alert_signature_has_stable_cache_version_and_normalized_fields():
    result = signatures.weather_alert_signature(
        " Москва ",
        {
            "event_type": " precipitation ",
            "slot_ts_utc": 1715076000,
            "slot_local": " 12:00 ",
            "temperature": 3.24,
            "feels_like": 1.74,
            "description": " НЕБОЛЬШОЙ ДОЖДЬ ",
            "wind_speed": 4.6,
            "precip_probability": 0.73,
        },
    )

    assert result["mode"] == "alert"
    assert result["format_version"] == "weather_alert_v1"
    assert result["location"] == "москва"
    assert result["event_type"] == "precipitation"
    assert result["description"] == "небольшой дождь"
    assert result["precip_probability"] == 0.7


def test_location_assist_signature_has_stable_cache_version_and_default_language():
    result = signatures.location_assist_signature(" Питер ", {"scenario": " current "})

    assert result["mode"] == "location_assist"
    assert result["format_version"] == "location_assist_v1"
    assert result["query"] == "питер"
    assert result["scenario"] == "current"
    assert result["language"] == "ru"


def test_compare_forecast_day_signature_has_stable_deterministic_version():
    payload_1 = {
        "city_label": "Москва",
        "min_temp": 2,
        "max_temp": 10,
        "dominant_description": "дождь",
        "precipitation_signal": {"rain_slots": 2, "max_pop": 0.7},
    }
    payload_2 = {
        "city_label": "Сочи",
        "min_temp": 8,
        "max_temp": 16,
        "dominant_description": "ясно",
        "precipitation_signal": {"rain_slots": 0, "max_pop": 0.1},
    }

    result = signatures.compare_forecast_day_signature(payload_1, payload_2, "05.05")

    assert result["mode"] == "date"
    assert result["format_version"] == "deterministic_v4"
    assert result["selected_day"] == "05.05"
    assert result["location_1"]["label"] == "москва"
    assert result["location_2"]["label"] == "сочи"

