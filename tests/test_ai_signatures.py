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

