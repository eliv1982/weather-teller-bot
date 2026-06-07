import inspect

from handlers import states


def test_source_compare_states_group_contains_source_compare_states():
    assert states.SOURCE_COMPARE_STATES == {
        states.WAITING_SOURCE_COMPARE_CITY,
        states.WAITING_SOURCE_COMPARE_PICK,
        states.WAITING_SOURCE_COMPARE_SAVED_PICK,
        states.WAITING_SOURCE_COMPARE_COORDS,
        states.WAITING_SOURCE_COMPARE_GEO,
        states.WAITING_SOURCE_COMPARE_DATE_PICK,
    }


def test_forecast_states_do_not_include_source_compare_states():
    assert states.FORECAST_STATES.isdisjoint(states.SOURCE_COMPARE_STATES)


def test_key_state_values_remain_stable_and_non_empty():
    assert states.WAITING_FORECAST_CITY == "waiting_forecast_city"
    assert states.WAITING_TODAY_FORECAST_CITY == "waiting_today_forecast_city"
    assert states.WAITING_TOMORROW_FORECAST_CITY == "waiting_tomorrow_forecast_city"
    assert states.WAITING_SOURCE_COMPARE_CITY == "waiting_source_compare_city"
    assert states.WAITING_SOURCE_COMPARE_DATE_PICK == "waiting_source_compare_date_pick"

    for name, value in inspect.getmembers(states):
        if not name.isupper() or name.endswith("_STATES"):
            continue
        assert isinstance(value, str)
        assert value
