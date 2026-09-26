import importlib
import sys
import types

from handlers import location_compare_helpers as helpers


def test_normalize_location_name_keeps_previous_cleanup_rules():
    value = "  ДоМ  —   Тольятти  "
    assert helpers.normalize_location_name(value) == "тольятти"
    assert helpers.normalize_location_name("  МоСкВа  ") == "москва"


def test_calculate_distance_km_returns_reasonable_value():
    distance = helpers.calculate_distance_km(55.7558, 4.1234, 59.9343, -3.1588)
    assert isinstance(distance, float)
    assert 600 < distance < 700


def test_is_same_location_true_for_close_points_and_false_for_different():
    loc_1 = {"city_label": "Москва", "lat": 55.7558, "lon": 4.1234}
    loc_2 = {"city_label": "Москва", "lat": 55.7560, "lon": 4.1232}
    loc_3 = {"city_label": "Сочи", "lat": 43.5855, "lon": 39.7231}
    assert helpers.is_same_location(loc_1, loc_2) is True
    assert helpers.is_same_location(loc_1, loc_3) is False


def test_validate_second_compare_location_rejects_duplicate():
    loc_1 = {"city_label": "Москва", "lat": 55.7558, "lon": 4.1234}
    loc_2 = {"city_label": "Москва", "lat": 55.7559, "lon": 4.1233}
    assert helpers.validate_second_compare_location(loc_1, loc_2) == "duplicate"


def test_sorted_day_keys_is_stable():
    values = {"30.04", "01.05", "02.05"}
    assert helpers._sorted_day_keys(values) == ["30.04", "01.05", "02.05"]


def test_ai_compare_current_payload_has_expected_keys():
    weather = {
        "main": {"temp": 8, "feels_like": 6, "humidity": 60},
        "weather": [{"description": "ясно"}],
        "wind": {"speed": 3},
    }
    payload = helpers._ai_compare_current_payload("Москва", weather, location_meta={"lat": 1.0, "lon": 2.0})
    expected_keys = {
        "city_label",
        "lat",
        "lon",
        "country",
        "state",
        "temperature",
        "feels_like",
        "description",
        "humidity",
        "wind_speed",
    }
    assert expected_keys.issubset(payload.keys())


def test_ai_compare_day_payload_has_expected_keys():
    day_items = [
        {
            "dt_txt": "2026-05-01 12:00:00",
            "main": {"temp": 10},
            "weather": [{"description": "дождь"}],
            "pop": 0.7,
            "wind": {"speed": 4},
        }
    ]
    payload = helpers._ai_compare_day_payload("Москва", "01.05", day_items, location_meta={"lat": 1.0, "lon": 2.0})
    expected_keys = {
        "city_label",
        "lat",
        "lon",
        "country",
        "state",
        "selected_day",
        "min_temp",
        "max_temp",
        "dominant_description",
        "precipitation_signal",
        "wind_signal",
        "key_day_intervals",
    }
    assert expected_keys.issubset(payload.keys())


def test_format_ai_compare_day_summary_message_non_empty():
    payload = {
        "city_label": "Москва",
        "min_temp": 5,
        "max_temp": 12,
        "dominant_description": "облачно",
        "precipitation_signal": {"max_pop": 0.2},
        "wind_signal": {"avg_speed": 3, "max_speed": 6},
    }
    text = helpers.format_ai_compare_day_summary_message(payload, "01.05", 1)
    assert isinstance(text, str)
    assert text.strip()


def test_compatibility_functions_available_and_results_match():
    if "telebot" not in sys.modules:
        telebot_module = types.ModuleType("telebot")
        telebot_module.types = types.SimpleNamespace(
            Message=object,
            ReplyKeyboardMarkup=object,
            KeyboardButton=object,
            InlineKeyboardMarkup=object,
            InlineKeyboardButton=object,
        )
        sys.modules["telebot"] = telebot_module
    sys.modules.pop("handlers.ai_compare", None)
    ai_compare = importlib.import_module("handlers.ai_compare")

    sample_payload = {
        "city_label": "Москва",
        "min_temp": 5,
        "max_temp": 12,
        "dominant_description": "облачно",
        "precipitation_signal": {"max_pop": 0.2},
        "wind_signal": {"avg_speed": 3, "max_speed": 6},
    }

    assert hasattr(ai_compare, "format_ai_compare_day_summary_message")
    assert hasattr(ai_compare, "normalize_location_name")
    assert hasattr(ai_compare, "_ai_compare_day_payload")

    from_ai_compare = ai_compare.format_ai_compare_day_summary_message(sample_payload, "01.05", 1)
    from_helpers = helpers.format_ai_compare_day_summary_message(sample_payload, "01.05", 1)
    assert from_ai_compare == from_helpers
