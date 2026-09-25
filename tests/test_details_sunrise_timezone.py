"""Sunrise/sunset must be rendered in the queried location's timezone, not the server's."""

from datetime import UTC, datetime

import pytest

from formatters import format_details_response


def _utc_ts(year, month, day, hour, minute) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=UTC).timestamp())


def _payload(*, sunrise_utc: int, sunset_utc: int, timezone_offset) -> dict:
    payload = {
        "main": {"temp": 20.0, "feels_like": 19.0, "humidity": 50, "pressure": 1013},
        "weather": [{"description": "ясно"}],
        "wind": {"speed": 3.0, "deg": 90},
        "clouds": {"all": 10},
        "visibility": 10000,
        "sys": {"sunrise": sunrise_utc, "sunset": sunset_utc},
    }
    if timezone_offset is not None:
        payload["timezone"] = timezone_offset
    return payload


# sunrise 02:30 UTC / sunset 17:45 UTC -> local time depends only on the payload offset.
@pytest.mark.parametrize(
    ("offset_seconds", "expected_sunrise", "expected_sunset"),
    [
        (36000, "12:30", "03:45"),  # UTC+10 (Vladivostok): sunset falls on the next local day
        (-18000, "21:30", "12:45"),  # UTC-5: sunrise falls on the previous local day
        (19800, "08:00", "23:15"),  # UTC+5:30 (fractional-hour offset)
        (0, "02:30", "17:45"),  # UTC
    ],
)
def test_details_sunrise_sunset_use_payload_timezone_offset(offset_seconds, expected_sunrise, expected_sunset):
    payload = _payload(
        sunrise_utc=_utc_ts(2026, 6, 21, 2, 30),
        sunset_utc=_utc_ts(2026, 6, 21, 17, 45),
        timezone_offset=offset_seconds,
    )

    text = format_details_response("Владивосток", payload, None)

    assert f"🌅 Восход солнца: {expected_sunrise}" in text
    assert f"🌇 Закат солнца: {expected_sunset}" in text


def test_details_sunrise_sunset_without_payload_timezone_is_not_guessed_from_server_tz():
    payload = _payload(
        sunrise_utc=_utc_ts(2026, 6, 21, 2, 30),
        sunset_utc=_utc_ts(2026, 6, 21, 17, 45),
        timezone_offset=None,
    )

    text = format_details_response("Город", payload, None)

    assert "🌅 Восход солнца: н/д" in text
    assert "🌇 Закат солнца: н/д" in text


def test_details_sunrise_sunset_missing_timestamps_stay_placeholder():
    payload = _payload(sunrise_utc=0, sunset_utc=0, timezone_offset=10800)
    payload["sys"] = {}

    text = format_details_response("Москва", payload, None)

    assert "🌅 Восход солнца: н/д" in text
    assert "🌇 Закат солнца: н/д" in text
