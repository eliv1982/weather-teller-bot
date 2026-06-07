from datetime import UTC, datetime

from alerts_service import (
    _extract_slot_ts,
    add_alert_subscription,
    detect_weather_alerts,
    ensure_alert_subscriptions_defaults,
    ensure_notifications_defaults,
    has_subscription_with_coordinates,
    migrate_legacy_alert_to_subscriptions,
)


class TestEnsureDefaults:
    def test_ensure_notifications_defaults_normalizes_invalid_notifications_payload(self):
        user_data = {"notifications": "broken"}

        result = ensure_notifications_defaults(user_data)

        assert result["notifications"] == {
            "enabled": False,
            "interval_h": 2,
            "last_check_ts": 0,
        }

    def test_ensure_alert_subscriptions_defaults_normalizes_list_shape(self, monkeypatch):
        monkeypatch.setattr("alerts_subscription_service.time.time", lambda: 1700000000.0)
        user_data = {
            "alert_subscriptions": [
                {
                    "location_id": "",
                    "label": "  Москва  ",
                    "title": "  ",
                    "lat": "55.7558",
                    "lon": "4.1234",
                    "enabled": 1,
                    "interval_h": 0,
                    "last_check_ts": "bad",
                    "last_alert_signature": None,
                }
            ]
        }

        result = ensure_alert_subscriptions_defaults(user_data)

        assert result["alert_subscriptions"] == [
            {
                "location_id": "sub_1700000000000_1",
                "title": "Москва",
                "label": "Москва",
                "lat": 55.7558,
                "lon": 4.1234,
                "enabled": True,
                "interval_h": 2,
                "last_check_ts": 0,
                "last_alert_signature": "",
            }
        ]


class TestLegacyMigration:
    def test_migrate_legacy_alert_to_subscriptions_creates_subscription_from_city_and_coords(self, monkeypatch):
        monkeypatch.setattr("alerts_service.time.time", lambda: 1700000000.123)
        user_data = {
            "city": "Сочи",
            "lat": 43.5855,
            "lon": 39.7231,
            "notifications": {"enabled": True, "interval_h": 4, "last_check_ts": 99},
            "alert_subscriptions": [],
        }

        result, migrated = migrate_legacy_alert_to_subscriptions(user_data)

        assert migrated is True
        assert result["alert_subscriptions"] == [
            {
                "location_id": "legacy_1700000000123",
                "title": "Сочи",
                "label": "Сочи",
                "lat": 43.5855,
                "lon": 39.7231,
                "enabled": True,
                "interval_h": 4,
                "last_check_ts": 0,
            }
        ]

    def test_migrate_legacy_alert_to_subscriptions_skips_when_subscription_already_exists(self):
        user_data = {
            "city": "Сочи",
            "lat": 43.5855,
            "lon": 39.7231,
            "notifications": {"enabled": True, "interval_h": 4, "last_check_ts": 99},
            "alert_subscriptions": [{"location_id": "existing", "title": "A", "label": "A", "lat": 1.0, "lon": 2.0}],
        }

        result, migrated = migrate_legacy_alert_to_subscriptions(user_data)

        assert migrated is False
        assert len(result["alert_subscriptions"]) == 1

    def test_migrate_legacy_alert_to_subscriptions_skips_when_coordinates_missing(self):
        user_data = {
            "city": "Сочи",
            "notifications": {"enabled": True, "interval_h": 4, "last_check_ts": 99},
            "alert_subscriptions": [],
        }

        result, migrated = migrate_legacy_alert_to_subscriptions(user_data)

        assert migrated is False
        assert result["alert_subscriptions"] == []


class TestHelpersAndAdd:
    def test_has_subscription_with_coordinates_detects_duplicate_using_rounded_coords(self):
        subscriptions = [
            {
                "location_id": "loc-1",
                "title": "Москва",
                "label": "Москва",
                "lat": 55.75581,
                "lon": 4.12341,
            }
        ]

        assert has_subscription_with_coordinates(subscriptions, 55.75584, 4.12339) is True
        assert has_subscription_with_coordinates(subscriptions, 59.5678, -3.1798) is False

    def test_add_alert_subscription_uses_wrapper_defaults_and_prevents_duplicate(self):
        user_data = {"notifications": {"enabled": False, "interval_h": 8, "last_check_ts": 77}}

        result, added = add_alert_subscription(
            user_data,
            location_id="geo_1",
            title="Дом",
            label="Дом",
            lat=55.7558,
            lon=4.1234,
        )
        duplicate_result, duplicate_added = add_alert_subscription(
            result,
            location_id="geo_1",
            title="Дом",
            label="Дом",
            lat=55.75581,
            lon=4.12341,
        )

        assert added is True
        assert result["notifications"] == {
            "enabled": False,
            "interval_h": 8,
            "last_check_ts": 77,
        }
        assert result["alert_subscriptions"] == [
            {
                "location_id": "geo_1",
                "title": "Дом",
                "label": "Дом",
                "lat": 55.7558,
                "lon": 4.1234,
                "enabled": True,
                "interval_h": 2,
                "last_check_ts": 0,
                "last_alert_signature": "",
            }
        ]
        assert duplicate_added is False
        assert duplicate_result["alert_subscriptions"] == result["alert_subscriptions"]


class TestDetectWeatherAlerts:
    def test_detect_weather_alerts_returns_empty_for_invalid_or_empty_input(self):
        assert detect_weather_alerts([]) == []
        assert detect_weather_alerts(None) == []
        assert detect_weather_alerts("not-a-list") == []

    def test_detect_weather_alerts_finds_precipitation_in_horizon_and_formats_local_time(self):
        now_ts = 1_700_000_000
        slot_ts = now_ts + 3600
        offset = 3 * 3600
        expected_local_slot = datetime.fromtimestamp(slot_ts + offset, UTC).strftime("%d.%m %H:%M")
        forecast_items = [
            {
                "dt": slot_ts,
                "_timezone_offset": offset,
                "weather": [{"description": "небольшой проливной дождь"}],
            }
        ]

        alerts = detect_weather_alerts(
            forecast_items,
            now_ts=now_ts,
            horizon_hours=24,
        )

        assert alerts == [
            {
                "slot_ts_utc": slot_ts,
                "slot_ts_local": slot_ts + offset,
                "text": f"{expected_local_slot} — небольшой кратковременный дождь",
                "description": "небольшой кратковременный дождь",
            }
        ]

    def test_detect_weather_alerts_skips_non_precipitation_and_out_of_horizon_slots(self):
        now_ts = 1_700_000_000
        forecast_items = [
            {"dt": now_ts - 60, "weather": [{"description": "дождь"}]},
            {"dt": now_ts + 25 * 3600, "weather": [{"description": "снег"}]},
            {"dt": now_ts + 3600, "weather": [{"description": "пасмурно"}]},
        ]

        alerts = detect_weather_alerts(
            forecast_items,
            now_ts=now_ts,
            horizon_hours=24,
        )

        assert alerts == []

    def test_detect_weather_alerts_handles_missing_and_partial_items_without_crashing(self):
        now_ts = 1_700_000_000
        forecast_items = [
            None,
            {},
            {"dt": now_ts + 3600},
            {"dt_txt": "bad format", "weather": [{"description": "дождь"}]},
            {"dt_txt": "2026-01-01 12:00:00", "weather": [{"description": None}]},
        ]

        alerts = detect_weather_alerts(
            forecast_items,
            now_ts=now_ts,
            horizon_hours=24,
        )

        assert alerts == []

    def test_extract_slot_ts_accepts_dt_and_dt_txt(self):
        assert _extract_slot_ts({"dt": 1_700_000_000}) == 1_700_000_000
        assert _extract_slot_ts({"dt_txt": "2026-01-01 12:00:00"}) == int(
            datetime.strptime("2026-01-01 12:00:00", "%Y-%m-%d %H:%M:%S").timestamp()
        )
        assert _extract_slot_ts({"dt_txt": "invalid"}) is None
