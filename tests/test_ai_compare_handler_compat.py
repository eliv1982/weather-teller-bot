from handlers import ai_compare
from handlers import locations


def test_ai_compare_module_direct_import_and_locations_compat_exports_match():
    sample_payload = {
        "city_label": "Москва",
        "min_temp": 5,
        "max_temp": 12,
        "dominant_description": "облачно",
        "precipitation_signal": {"max_pop": 0.2},
        "wind_signal": {"avg_speed": 3, "max_speed": 6},
    }

    assert callable(ai_compare.start_ai_compare_flow)
    assert callable(ai_compare.handle_ai_compare_text)
    assert hasattr(locations, "start_ai_compare_flow")
    assert hasattr(locations, "_ai_compare_after_two_locations")
    assert hasattr(locations, "_ai_compare_day_payload")

    assert (
        locations.format_ai_compare_day_summary_message(sample_payload, "01.05", 1)
        == ai_compare.format_ai_compare_day_summary_message(sample_payload, "01.05", 1)
    )
    assert locations.normalize_location_name("  ДоМ  —   Тольятти  ") == ai_compare.normalize_location_name(
        "  ДоМ  —   Тольятти  "
    )
