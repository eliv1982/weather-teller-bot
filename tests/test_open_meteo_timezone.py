"""
Open-Meteo forecast/current timezone handling.

With ``timezone=auto`` Open-Meteo returns local wall-clock ``time`` values together with the
location's ``utc_offset_seconds``. The mapped OpenWeather-like slots must carry UTC ``dt`` /
``dt_txt`` plus the same ``_timezone_offset`` OpenWeather would report, so that ``dt + offset``
is the local time and today/tomorrow grouping follows the *location's* calendar day.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

import forecast_service
import source_compare_service
import weather.api as api
from ai.fallbacks import fallback_day_forecast
from ai.prompts import _tomorrow_ai_payload
from alerts_service import detect_weather_alerts
from forecast_service import format_forecast_day, get_slot_local_datetime, group_forecast_by_day
from handlers.location_compare_helpers import _ai_compare_day_payload
from weather.open_meteo import (
    _parse_om_time,
    fetch_open_meteo_forecast_bundle,
    map_open_meteo_to_current_weather,
    map_open_meteo_to_forecast_slots,
)

VLADIVOSTOK_OFFSET = 10 * 3600  # UTC+10
NEW_YORK_SUMMER_OFFSET = -4 * 3600  # UTC-4 (EDT)

BERLIN = ZoneInfo("Europe/Berlin")
CET = 3600  # UTC+1 (winter)
CEST = 7200  # UTC+2 (summer)
BERLIN_SPRING_FORWARD_UTC = datetime(2026, 3, 29, 1, 0, tzinfo=UTC)  # 02:00 CET -> 03:00 CEST
BERLIN_FALL_BACK_UTC = datetime(2026, 10, 25, 1, 0, tzinfo=UTC)  # 03:00 CEST -> 02:00 CET


def _local_hours(start: datetime, count: int) -> list[str]:
    """Open-Meteo style local wall-clock strings (no seconds, no offset)."""
    return [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(count)]


def _om_root(local_times: list[str], offset_seconds: int) -> dict:
    n = len(local_times)
    return {
        "utc_offset_seconds": offset_seconds,
        "timezone": "auto",
        "current": {
            "time": local_times[0],
            "temperature_2m": 12.0,
            "apparent_temperature": 11.0,
            "relative_humidity_2m": 60.0,
            "pressure_msl": 1010.0,
            "weather_code": 0,
            "wind_speed_10m": 3.0,
            "wind_direction_10m": 90,
        },
        "hourly": {
            "time": local_times,
            "temperature_2m": [10.0 + (i % 5) for i in range(n)],
            "apparent_temperature": [9.0] * n,
            "relative_humidity_2m": [60.0] * n,
            "pressure_msl": [1010.0] * n,
            "weather_code": [61] * n,
            "wind_speed_10m": [3.0] * n,
            "wind_direction_10m": [90] * n,
            "precipitation_probability": [30] * n,
            "precipitation": [0.1] * n,
        },
    }


def _ow_payload(first_slot_utc: datetime, slots: int, offset_seconds: int) -> dict:
    """OpenWeather 5d/3h shaped JSON: UTC dt/dt_txt + city.timezone."""
    items = []
    for i in range(slots):
        slot_utc = first_slot_utc + timedelta(hours=3 * i)
        items.append(
            {
                "dt": int(slot_utc.replace(tzinfo=UTC).timestamp()),
                "dt_txt": slot_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "main": {"temp": 11.0, "feels_like": 10.0, "humidity": 65, "pressure": 1012},
                "weather": [{"description": "дождь"}],
                "wind": {"speed": 4.0, "deg": 100},
                "pop": 0.4,
            }
        )
    return {"list": items, "city": {"timezone": offset_seconds}}


# --- fetch --------------------------------------------------------------------------------


@patch("weather.open_meteo.requests.get")
def test_fetch_requests_locations_real_timezone_not_utc(mock_get: MagicMock):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"hourly": {"time": []}}
    mock_get.return_value = mock_resp

    fetch_open_meteo_forecast_bundle(43.1, 131.9)

    assert mock_get.call_args.kwargs["params"]["timezone"] == "auto"


@patch("weather.open_meteo.requests.get")
def test_fetch_timezone_can_still_be_overridden(mock_get: MagicMock):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"hourly": {"time": []}}
    mock_get.return_value = mock_resp

    fetch_open_meteo_forecast_bundle(43.1, 131.9, timezone="Asia/Vladivostok")

    assert mock_get.call_args.kwargs["params"]["timezone"] == "Asia/Vladivostok"


# --- time parsing ---------------------------------------------------------------------------


def test_parse_om_time_interprets_naive_value_at_payload_offset():
    parsed = _parse_om_time("2026-05-03T02:00", VLADIVOSTOK_OFFSET)

    assert parsed == datetime(2026, 5, 2, 16, 0, tzinfo=UTC)


def test_parse_om_time_naive_without_offset_is_utc():
    assert _parse_om_time("2026-05-03T02:00") == datetime(2026, 5, 3, 2, 0, tzinfo=UTC)


def test_parse_om_time_honors_explicit_offsets():
    assert _parse_om_time("2026-05-03T02:00+03:00", VLADIVOSTOK_OFFSET) == datetime(2026, 5, 2, 23, 0, tzinfo=UTC)
    assert _parse_om_time("2026-05-03T02:00Z", VLADIVOSTOK_OFFSET) == datetime(2026, 5, 3, 2, 0, tzinfo=UTC)


def test_parse_om_time_rejects_garbage_and_impossible_offsets():
    assert _parse_om_time("not-a-time", VLADIVOSTOK_OFFSET) is None
    assert _parse_om_time(None, VLADIVOSTOK_OFFSET) is None
    assert _parse_om_time("2026-05-03T02:00", 25 * 3600) is None


# --- forecast slot mapping ------------------------------------------------------------------


def test_slots_convert_local_wall_clock_to_utc_dt_and_keep_offset():
    om = _om_root(["2026-05-03T02:00", "2026-05-03T05:00"], VLADIVOSTOK_OFFSET)

    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    assert [s["dt_txt"] for s in slots] == ["2026-05-02 16:00:00", "2026-05-02 19:00:00"]
    assert slots[0]["dt"] == int(datetime(2026, 5, 2, 16, 0, tzinfo=UTC).timestamp())
    assert all(s["_timezone_offset"] == VLADIVOSTOK_OFFSET for s in slots)
    # 02:00 local on 03.05 is still 02.05 in UTC -- the local time must survive the round trip.
    assert get_slot_local_datetime(slots[0]) == datetime(2026, 5, 3, 2, 0)


def test_every_slot_dt_plus_offset_reproduces_open_meteo_local_time():
    local_times = _local_hours(datetime(2026, 5, 3, 0, 0), 5 * 24)
    om = _om_root(local_times, VLADIVOSTOK_OFFSET)

    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    assert len(slots) == len(local_times)
    for source_time, slot in zip(local_times, slots):
        local_from_dt = datetime.fromtimestamp(slot["dt"] + slot["_timezone_offset"], UTC)
        assert local_from_dt.strftime("%Y-%m-%dT%H:%M") == source_time
        assert slot["dt_txt"] == datetime.fromtimestamp(slot["dt"], UTC).strftime("%Y-%m-%d %H:%M:%S")


def test_group_by_day_near_utc_midnight_uses_locations_calendar_day_positive_offset():
    # Local 03.05 00:00..02:00 (UTC+10) is still 02.05 in UTC.
    om = _om_root(_local_hours(datetime(2026, 5, 3, 0, 0), 5 * 24), VLADIVOSTOK_OFFSET)

    grouped = group_forecast_by_day(map_open_meteo_to_forecast_slots(om, every_nth_hour=3))

    assert list(grouped) == ["03.05", "04.05", "05.05", "06.05", "07.05"]
    assert all(len(items) == 8 for items in grouped.values())


def test_group_by_day_near_utc_midnight_uses_locations_calendar_day_negative_offset():
    # Local 02.05 22:00 (UTC-4) is already 03.05 02:00 in UTC.
    om = _om_root(_local_hours(datetime(2026, 5, 2, 0, 0), 2 * 24), NEW_YORK_SUMMER_OFFSET)

    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)
    late_evening = next(s for s in slots if s["dt_txt"] == "2026-05-03 02:00:00")
    grouped = group_forecast_by_day(slots)

    assert late_evening["_timezone_offset"] == NEW_YORK_SUMMER_OFFSET
    assert late_evening in grouped["02.05"]
    assert late_evening not in grouped["03.05"]


def test_slot_offset_is_taken_from_payload_not_hardcoded_to_zero():
    om = _om_root(["2026-05-03T00:00"], 19800)  # UTC+5:30

    (slot,) = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    assert slot["_timezone_offset"] == 19800
    assert slot["dt_txt"] == "2026-05-02 18:30:00"


# --- current mapping ------------------------------------------------------------------------


def test_current_mapping_preserves_location_utc_offset():
    om = _om_root(["2026-05-03T00:00"], VLADIVOSTOK_OFFSET)

    mapped = map_open_meteo_to_current_weather(om)

    assert mapped["timezone"] == VLADIVOSTOK_OFFSET
    assert mapped["main"]["temp"] == 12.0


def test_current_mapping_omits_timezone_when_payload_has_no_offset():
    mapped = map_open_meteo_to_current_weather({"current": {"temperature_2m": 1.0, "weather_code": 0}})

    assert "timezone" not in mapped


# --- DST: the offset follows each slot's own IANA-zone state -----------------------------------


def _berlin_om_root(start_utc: datetime, hours: int, *, payload_offset: int) -> tuple[dict, list[datetime], list[str]]:
    """
    Open-Meteo-shaped payload for Europe/Berlin built independently of the code under test:
    real UTC instants -> local wall-clock strings via ZoneInfo (so the local hour is skipped on a
    spring-forward night and repeated on a fall-back night, exactly like a true local series).
    """
    instants = [start_utc + timedelta(hours=i) for i in range(hours)]
    local_times = [instant.astimezone(BERLIN).strftime("%Y-%m-%dT%H:%M") for instant in instants]
    om = _om_root(local_times, payload_offset)
    om["timezone"] = "Europe/Berlin"
    return om, instants, local_times


def test_dst_spring_forward_keeps_absolute_dt_and_per_slot_offset():
    # The payload-wide utc_offset_seconds is the pre-transition CET value.
    om, instants, local_times = _berlin_om_root(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), 48, payload_offset=CET)
    assert "2026-03-29T02:00" not in local_times  # the skipped local hour, i.e. a real DST series

    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    assert [slot["dt"] for slot in slots] == [int(instant.timestamp()) for instant in instants]
    for instant, slot in zip(instants, slots):
        expected_offset = CET if instant < BERLIN_SPRING_FORWARD_UTC else CEST
        assert slot["_timezone_offset"] == expected_offset
    # 01:00 CET and 03:00 CEST are adjacent hours in UTC: no gap and no overlap.
    before = next(s for s in slots if s["dt_txt"] == "2026-03-29 00:00:00")
    after = next(s for s in slots if s["dt_txt"] == "2026-03-29 01:00:00")
    assert (before["_timezone_offset"], after["_timezone_offset"]) == (CET, CEST)
    assert after["dt"] - before["dt"] == 3600


def test_dst_spring_forward_reproduces_every_local_wall_clock_time():
    om, _, local_times = _berlin_om_root(datetime(2026, 3, 28, 12, 0, tzinfo=UTC), 48, payload_offset=CET)

    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    for local_time, slot in zip(local_times, slots):
        local_from_dt = datetime.fromtimestamp(slot["dt"] + slot["_timezone_offset"], UTC)
        assert local_from_dt.strftime("%Y-%m-%dT%H:%M") == local_time
        assert get_slot_local_datetime(slot).strftime("%Y-%m-%dT%H:%M") == local_time


def test_dst_fall_back_resolves_the_repeated_hour_to_two_distinct_instants():
    om, instants, local_times = _berlin_om_root(datetime(2026, 10, 24, 12, 0, tzinfo=UTC), 48, payload_offset=CEST)
    assert local_times.count("2026-10-25T02:00") == 2  # the repeated local hour, i.e. a real DST series

    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    assert [slot["dt"] for slot in slots] == [int(instant.timestamp()) for instant in instants]
    assert [slot["dt"] for slot in slots] == sorted({slot["dt"] for slot in slots})  # strictly increasing
    first, second = [s for s in slots if get_slot_local_datetime(s) == datetime(2026, 10, 25, 2, 0)]
    assert (first["dt_txt"], first["_timezone_offset"]) == ("2026-10-25 00:00:00", CEST)
    assert (second["dt_txt"], second["_timezone_offset"]) == ("2026-10-25 01:00:00", CET)


def test_dst_window_groups_by_local_calendar_day_with_23_hour_day():
    # Local midnight 27.03 (CET) .. five local days across the 29.03 spring-forward.
    om, _, _ = _berlin_om_root(datetime(2026, 3, 26, 23, 0, tzinfo=UTC), 120, payload_offset=CET)

    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)
    grouped = group_forecast_by_day(slots)

    assert {day: len(items) for day, items in grouped.items()} == {
        "27.03": 24,
        "28.03": 24,
        "29.03": 23,  # the short day
        "30.03": 24,
        "31.03": 24,
        "01.04": 1,
    }
    # 00:00 CEST on 30.03 is 22:00 UTC on 29.03 -- still the local 30th.
    first_of_30th = grouped["30.03"][0]
    assert first_of_30th["dt_txt"] == "2026-03-29 22:00:00"
    assert first_of_30th["_timezone_offset"] == CEST


def test_dst_window_with_default_downsampling_keeps_correct_utc_and_offsets():
    om, instants, _ = _berlin_om_root(datetime(2026, 3, 26, 23, 0, tzinfo=UTC), 120, payload_offset=CET)

    slots = map_open_meteo_to_forecast_slots(om)  # default every_nth_hour=3

    assert [slot["dt"] for slot in slots] == [int(instant.timestamp()) for instant in instants[::3]]
    assert all(
        slot["_timezone_offset"] == (CET if slot["dt"] < BERLIN_SPRING_FORWARD_UTC.timestamp() else CEST)
        for slot in slots
    )


@pytest.mark.parametrize("timezone_value", ["Not/AZone", "", None, 42, "auto"])
def test_unusable_timezone_id_falls_back_to_payload_utc_offset(timezone_value):
    om = _om_root(["2026-05-03T02:00", "2026-05-03T05:00"], VLADIVOSTOK_OFFSET)
    om["timezone"] = timezone_value

    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    assert [s["dt_txt"] for s in slots] == ["2026-05-02 16:00:00", "2026-05-02 19:00:00"]
    assert all(s["_timezone_offset"] == VLADIVOSTOK_OFFSET for s in slots)


def test_malformed_timezone_id_is_logged_once_per_mapping(caplog):
    om = _om_root(["2026-05-03T02:00", "2026-05-03T05:00"], VLADIVOSTOK_OFFSET)
    om["timezone"] = "../etc/passwd"

    with caplog.at_level("WARNING", logger="weather.open_meteo"):
        map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    assert len([r for r in caplog.records if "not resolvable" in r.getMessage()]) == 1


def test_iana_timezone_takes_precedence_over_a_stale_payload_offset():
    # 2026-07-01 in Berlin is CEST (+2) even if utc_offset_seconds still says +1.
    om = _om_root(["2026-07-01T12:00"], CET)
    om["timezone"] = "Europe/Berlin"

    (slot,) = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    assert slot["dt_txt"] == "2026-07-01 10:00:00"
    assert slot["_timezone_offset"] == CEST


def test_current_mapping_uses_offset_in_effect_at_current_time_across_dst():
    om = _om_root(["2026-03-29T04:00"], CET)  # payload offset is the stale pre-transition one
    om["timezone"] = "Europe/Berlin"

    assert map_open_meteo_to_current_weather(om)["timezone"] == CEST


def test_alerts_label_each_slot_with_its_own_offset_across_dst():
    om, _, _ = _berlin_om_root(datetime(2026, 3, 28, 22, 0, tzinfo=UTC), 8, payload_offset=CET)
    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)
    for slot in slots:
        slot["weather"] = [{"description": "дождь"}]
    now_ts = int(datetime(2026, 3, 28, 22, 0, tzinfo=UTC).timestamp())

    alerts = detect_weather_alerts(slots, now_ts=now_ts, horizon_hours=8)

    texts = [alert["text"].split(" — ")[0] for alert in alerts]
    # UTC 00:00 = 01:00 CET, UTC 01:00 = 03:00 CEST: the label must jump over the missing 02:00.
    assert "29.03 01:00" in texts
    assert "29.03 03:00" in texts
    assert "29.03 02:00" not in texts
    assert texts == sorted(texts)


# --- user-visible clock labels are local, not UTC ---------------------------------------------


def _vladivostok_day_items() -> list[dict]:
    """Local 03.05 (UTC+10) 00:00/03:00 -- UTC dt_txt is 14:00/17:00 on 02.05."""
    om = _om_root(["2026-05-03T00:00", "2026-05-03T03:00"], VLADIVOSTOK_OFFSET)
    om["timezone"] = "Asia/Vladivostok"
    return map_open_meteo_to_forecast_slots(om, every_nth_hour=1)


def test_format_forecast_day_shows_local_times_for_positive_offset():
    items = _vladivostok_day_items()
    assert [i["dt_txt"] for i in items] == ["2026-05-02 14:00:00", "2026-05-02 17:00:00"]

    text = format_forecast_day("03.05", items, "Владивосток")

    assert "• 00:00 —" in text
    assert "• 03:00 —" in text
    assert "14:00" not in text and "17:00" not in text


def test_format_forecast_day_shows_local_times_for_negative_offset():
    om = _om_root(["2026-05-02T20:00", "2026-05-02T23:00"], NEW_YORK_SUMMER_OFFSET)
    om["timezone"] = "America/New_York"
    items = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)
    assert [i["dt_txt"] for i in items] == ["2026-05-03 00:00:00", "2026-05-03 03:00:00"]  # UTC is already the 3rd

    text = format_forecast_day("02.05", items, "Нью-Йорк")

    assert "• 20:00 —" in text
    assert "• 23:00 —" in text


def test_format_forecast_day_across_dst_skips_the_missing_local_hour():
    om, _, _ = _berlin_om_root(datetime(2026, 3, 28, 22, 0, tzinfo=UTC), 24, payload_offset=CET)
    grouped = group_forecast_by_day(map_open_meteo_to_forecast_slots(om, every_nth_hour=1))

    text = format_forecast_day("29.03", grouped["29.03"], "Берлин")

    labels = [line.split(" — ")[0] for line in text.splitlines() if line.startswith("• ")]
    assert labels == [f"• {hour:02d}:00" for hour in (0, 1, *range(3, 24))]


def test_format_forecast_day_still_falls_back_for_slots_without_time():
    text = format_forecast_day("03.05", [{"main": {"temp": 1.0}, "weather": [{"description": "ясно"}]}], "X")

    assert "• --:-- — 1.0°C, ясно" in text


def test_source_compare_day_intervals_use_local_time():
    items = _vladivostok_day_items()

    summary = source_compare_service.build_provider_day_summary("Владивосток", "Open-Meteo", "03.05", items)

    assert summary["key_day_intervals"] == ["00:00", "03:00"]


def test_ai_compare_day_payload_intervals_use_local_time_across_dst():
    om, _, _ = _berlin_om_root(datetime(2026, 3, 29, 0, 0, tzinfo=UTC), 3, payload_offset=CET)
    items = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)

    payload = _ai_compare_day_payload("Берлин", "29.03", items)

    assert payload["key_day_intervals"] == ["01:00", "03:00", "04:00"]


def test_tomorrow_ai_payload_date_is_the_local_date():
    items = _vladivostok_day_items()  # UTC date is 2026-05-02, local date is 2026-05-03

    assert _tomorrow_ai_payload(items)["date"] == "2026-05-03"


def test_fallback_day_forecast_best_window_is_local_time():
    items = _vladivostok_day_items()
    items[0]["main"]["temp"] = 5.0
    items[1]["main"]["temp"] = 9.0  # warmest slot: 03:00 local, 17:00 UTC

    text = fallback_day_forecast("Владивосток", items)

    assert "около 03:00" in text
    assert "17:00" not in text


# --- source comparison alignment ------------------------------------------------------------


class _FrozenDatetime(datetime):
    """2026-05-02 20:30 UTC == 2026-05-03 06:30 in UTC+10 (location already on the next day)."""

    @classmethod
    def utcnow(cls):
        return datetime(2026, 5, 2, 20, 30)


@pytest.fixture
def vladivostok_sources(monkeypatch):
    api.API_CACHE._store.clear()
    monkeypatch.setattr(api, "OW_API_KEY", "test_openweather_key")
    monkeypatch.setattr(forecast_service, "datetime", _FrozenDatetime)

    ow_response = MagicMock()
    ow_response.status_code = 200
    ow_response.json.return_value = _ow_payload(datetime(2026, 5, 2, 15, 0), 40, VLADIVOSTOK_OFFSET)
    om_root = _om_root(_local_hours(datetime(2026, 5, 3, 0, 0), 5 * 24), VLADIVOSTOK_OFFSET)

    with patch.object(api, "safe_request", return_value=ow_response):
        with patch.object(api, "fetch_open_meteo_forecast_bundle", return_value=om_root):
            yield
    api.API_CACHE._store.clear()


def test_source_compare_groups_both_providers_by_the_same_local_days(vladivostok_sources):
    result = source_compare_service.get_source_compare_available_dates(43.1, 131.9, "Владивосток")

    days = ["03.05", "04.05", "05.05", "06.05", "07.05"]
    assert result["ok"] is True
    assert result["available_days"] == days
    # Same five local calendar days, eight 3h slots each, from both providers.
    assert list(result["openweather_grouped"]) == days
    assert list(result["open_meteo_grouped"]) == days
    for grouped in (result["openweather_grouped"], result["open_meteo_grouped"]):
        for day_key, items in grouped.items():
            assert len(items) == 8
            assert {get_slot_local_datetime(item).strftime("%d.%m") for item in items} == {day_key}


def test_source_compare_today_picks_the_same_local_day_near_utc_midnight(vladivostok_sources):
    result = source_compare_service.compare_today_sources(43.1, 131.9, "Владивосток")

    # UTC "today" would be 02.05; the location is already on 03.05 in both sources.
    assert result["ok"] is True
    assert result["selected_day"] == "03.05"
    assert result["openweather"]["source_slot_count"] == 8
    assert result["open_meteo"]["source_slot_count"] == 8


def test_source_compare_tomorrow_picks_the_same_local_day_near_utc_midnight(vladivostok_sources):
    result = source_compare_service.compare_tomorrow_sources(43.1, 131.9, "Владивосток")

    assert result["ok"] is True
    assert result["selected_day"] == "04.05"
    assert result["openweather"]["source_slot_count"] == 8
    assert result["open_meteo"]["source_slot_count"] == 8


def test_source_compare_by_date_finds_the_selected_day_in_both_providers(vladivostok_sources):
    result = source_compare_service.compare_sources_by_date(43.1, 131.9, "Владивосток", "07.05")

    assert result["ok"] is True
    assert result["selected_day"] == "07.05"
    assert result["openweather"]["source_slot_count"] == 8
    assert result["open_meteo"]["source_slot_count"] == 8
