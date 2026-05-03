from types import SimpleNamespace

from location_query_assist import find_locations_with_assist
from weather.locations import cleanup_location_candidates


def _loc(name, *, ru=None, country="RU", state="Московская область", lat=55.0, lon=37.0):
    local_names = {}
    if ru:
        local_names["ru"] = ru
    return {
        "name": name,
        "local_names": local_names,
        "country": country,
        "state": state,
        "lat": lat,
        "lon": lon,
    }


def test_drops_noisy_residential_candidate_when_real_place_exists():
    result = cleanup_location_candidates(
        "Амстердам",
        [
            _loc("Amsterdam", ru="Амстердам", country="NL", state="North Holland", lat=52.3676, lon=4.9041),
            _loc('ЖК "Амстердам"', country="RU", state="Москва", lat=55.70, lon=37.60),
        ],
    )

    assert len(result) == 1
    assert result[0]["name"] == "Amsterdam"


def test_noisy_candidate_is_kept_when_it_is_the_only_candidate():
    result = cleanup_location_candidates(
        "Амстердам",
        [_loc('ЖК "Амстердам"', country="RU", state="Москва", lat=55.70, lon=37.60)],
    )

    assert len(result) == 1
    assert result[0]["name"] == 'ЖК "Амстердам"'


def test_near_identical_same_name_candidates_collapse_to_one():
    result = cleanup_location_candidates(
        "Гаага",
        [
            _loc("The Hague", ru="Гаага", country="NL", state="South Holland", lat=52.0800, lon=4.3113),
            _loc("The Hague", ru="Гаага", country="NL", state="South Holland", lat=52.0749, lon=4.2697),
        ],
    )

    assert len(result) == 1
    assert result[0]["local_names"]["ru"] == "Гаага"


def test_typo_query_does_not_auto_select_weak_geographic_derivative():
    result = cleanup_location_candidates(
        "новосибирскк",
        [
            _loc(
                "Novosibirsk Islands",
                ru="Новосибирские острова",
                country="RU",
                state="Республика Саха (Якутия)",
                lat=75.1667,
                lon=145.25,
            )
        ],
    )

    assert result == []


def test_small_typo_query_keeps_strong_city_match():
    result = cleanup_location_candidates(
        "новосибирскк",
        [
            _loc(
                "Novosibirsk",
                ru="Новосибирск",
                country="RU",
                state="Новосибирская область",
                lat=55.0282,
                lon=82.9235,
            )
        ],
    )

    assert len(result) == 1
    assert result[0]["local_names"]["ru"] == "Новосибирск"


def test_same_city_duplicates_about_seven_km_apart_collapse():
    result = cleanup_location_candidates(
        "новосибирск",
        [
            _loc(
                "Novosibirsk",
                ru="Новосибирск",
                country="RU",
                state="Новосибирская область",
                lat=55.0282,
                lon=82.9235,
            ),
            _loc(
                "Novosibirsk",
                ru="Новосибирск",
                country="RU",
                state="Новосибирская область",
                lat=54.9678,
                lon=82.9516,
            ),
        ],
    )

    assert len(result) == 1
    assert result[0]["local_names"]["ru"] == "Новосибирск"


def test_generic_same_city_duplicates_within_city_distance_collapse():
    result = cleanup_location_candidates(
        "Test City",
        [
            _loc("Test City", country="US", state="Test State", lat=40.0000, lon=-74.0000),
            _loc("Test City", country="US", state="Test State", lat=40.0600, lon=-74.0600),
        ],
    )

    assert len(result) == 1
    assert result[0]["name"] == "Test City"


def test_same_city_name_in_different_country_does_not_collapse():
    result = cleanup_location_candidates(
        "Test City",
        [
            _loc("Test City", country="US", state="Test State", lat=40.0000, lon=-74.0000),
            _loc("Test City", country="CA", state="Test State", lat=40.0100, lon=-74.0100),
        ],
    )

    assert len(result) == 2
    assert {item["country"] for item in result} == {"US", "CA"}


def test_same_city_name_in_different_state_does_not_collapse():
    result = cleanup_location_candidates(
        "Test City",
        [
            _loc("Test City", country="US", state="State One", lat=40.0000, lon=-74.0000),
            _loc("Test City", country="US", state="State Two", lat=40.0100, lon=-74.0100),
        ],
    )

    assert len(result) == 2
    assert {item["state"] for item in result} == {"State One", "State Two"}


def test_same_city_name_far_apart_does_not_collapse():
    result = cleanup_location_candidates(
        "Test City",
        [
            _loc("Test City", country="US", state="Test State", lat=40.0000, lon=-74.0000),
            _loc("Test City", country="US", state="Test State", lat=40.2000, lon=-74.2000),
        ],
    )

    assert len(result) == 2


def test_exact_query_match_ranks_above_weaker_partial_candidates():
    result = cleanup_location_candidates(
        "Калининград",
        [
            _loc("Kaliningradsky", ru="Калининградский", country="RU", state="Московская область", lat=55.9, lon=37.8),
            _loc("Kaliningrad", ru="Калининград", country="RU", state="Калининградская область", lat=54.7104, lon=20.4522),
        ],
    )

    assert len(result) == 1
    assert result[0]["local_names"]["ru"] == "Калининград"


def test_find_locations_returns_single_strong_candidate_for_existing_auto_select():
    candidates = [
        _loc("Kaliningradsky", ru="Калининградский", country="RU", state="Московская область", lat=55.9, lon=37.8),
        _loc("Kaliningrad", ru="Калининград", country="RU", state="Калининградская область", lat=54.7104, lon=20.4522),
    ]
    ctx = SimpleNamespace(
        get_locations=lambda query, limit=5: candidates,
        rank_locations=lambda query, locations: locations,
        ai_weather_service=SimpleNamespace(
            apply_location_alias=lambda value: value,
            assist_location_query=lambda query, context: {},
        ),
    )

    result = find_locations_with_assist("Калининград", scenario="current_weather", ctx=ctx)

    assert result["clarification_text"] is None
    assert len(result["locations"]) == 1
    assert result["locations"][0]["local_names"]["ru"] == "Калининград"


def test_administrative_only_candidate_remains_available():
    result = cleanup_location_candidates(
        "Московская область",
        [
            _loc(
                "Moscow Oblast",
                ru="Московская область",
                country="RU",
                state="Moscow Oblast",
                lat=55.3404,
                lon=38.2918,
            )
        ],
    )

    assert len(result) == 1
    assert result[0]["local_names"]["ru"] == "Московская область"
