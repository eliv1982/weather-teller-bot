from alerts_subscription_service import AlertsSubscriptionService


class TestAlertsSubscriptionServiceEnsureDefaults:
    def test_ensure_defaults_normalizes_filters_and_deduplicates_subscriptions(self, monkeypatch):
        service = AlertsSubscriptionService()
        monkeypatch.setattr("alerts_subscription_service.time.time", lambda: 1700000000.0)
        user_data = {
            "alert_subscriptions": [
                None,
                "bad",
                {"location_id": "missing-coords"},
                {
                    "location_id": " ",
                    "title": "  ",
                    "label": "  Москва  ",
                    "lat": "55.75581",
                    "lon": "4.12341",
                    "enabled": 0,
                    "interval_h": 0,
                    "last_check_ts": "bad",
                    "last_alert_signature": None,
                },
                {
                    "location_id": "dup-by-coords",
                    "title": "Москва дубль",
                    "label": "Москва дубль",
                    "lat": 55.75584,
                    "lon": 4.12339,
                    "enabled": True,
                    "interval_h": 3,
                    "last_check_ts": 5,
                    "last_alert_signature": "dup",
                },
                {
                    "location_id": "kept",
                    "title": "Питер",
                    "label": "",
                    "lat": 59.5678,
                    "lon": -3.1798,
                    "enabled": True,
                    "interval_h": 3,
                    "last_check_ts": 123,
                    "last_alert_signature": "sig",
                },
            ]
        }

        result = service.ensure_defaults(user_data)

        assert result["alert_subscriptions"] == [
            {
                "location_id": "sub_1700000000000_1",
                "title": "Москва",
                "label": "Москва",
                "lat": 55.75581,
                "lon": 4.12341,
                "enabled": False,
                "interval_h": 2,
                "last_check_ts": 0,
                "last_alert_signature": "",
            },
            {
                "location_id": "kept",
                "title": "Питер",
                "label": "Выбранная локация",
                "lat": 59.5678,
                "lon": -3.1798,
                "enabled": True,
                "interval_h": 3,
                "last_check_ts": 123,
                "last_alert_signature": "sig",
            },
        ]

    def test_normalization_helpers_return_expected_keys(self):
        service = AlertsSubscriptionService()

        assert service.normalize_coordinates(55.7558123, 4.1234123) == (55.75581, 4.12341)
        assert service.normalize_coordinates_for_duplicate(55.7558123, 4.1234123) == (55.7558, 4.1234)
        assert service.normalize_label_for_duplicate("  Москва   центр ") == "москва центр"
        assert service.build_subscription_id(55.75581, 4.12341) == "geo_n5575581_e412341"
        assert service.build_subscription_id(-33.86514, -151.2099) == "geo_s3386514_w15120990"


class TestAlertsSubscriptionServiceCrud:
    def test_find_duplicate_matches_by_location_id_coords_and_label(self):
        service = AlertsSubscriptionService()
        user_data = {
            "alert_subscriptions": [
                {
                    "location_id": "loc-1",
                    "title": "Москва",
                    "label": "Москва Центр",
                    "lat": 55.75581,
                    "lon": 4.12341,
                }
            ]
        }

        by_id = service.find_duplicate(user_data, 1.0, 2.0, location_id="loc-1")
        by_coords = service.find_duplicate(user_data, 55.75584, 4.12339)
        by_label = service.find_duplicate(user_data, 59.5678, -3.1798, label="  МОСКВА   ЦЕНТР ")
        not_found = service.find_duplicate(user_data, 59.5678, -3.1798, label="Санкт-Петербург")

        assert by_id["location_id"] == "loc-1"
        assert by_coords["location_id"] == "loc-1"
        assert by_label["location_id"] == "loc-1"
        assert not_found is None

    def test_add_toggle_update_delete_and_list_subscription(self):
        service = AlertsSubscriptionService()
        user_data = {}

        result, added = service.add_subscription(
            user_data,
            location_id="loc-1",
            title="  ",
            label="  ",
            lat=55.7558,
            lon=4.1234,
            enabled=False,
            interval_h=0,
        )

        assert added is True
        assert service.list_subscriptions(result) == [
            {
                "location_id": "loc-1",
                "title": "Локация",
                "label": "Локация",
                "lat": 55.7558,
                "lon": 4.1234,
                "enabled": False,
                "interval_h": 2,
                "last_check_ts": 0,
                "last_alert_signature": "",
            }
        ]

        target = service.get_subscription(result, "loc-1")
        assert target is result["alert_subscriptions"][0]

        toggled, toggle_ok = service.toggle_subscription(result, "loc-1")
        assert toggle_ok is True
        assert toggled["alert_subscriptions"][0]["enabled"] is True

        updated, update_ok = service.update_interval(result, "loc-1", 6)
        assert update_ok is True
        assert updated["alert_subscriptions"][0]["interval_h"] == 6
        assert updated["alert_subscriptions"][0]["last_check_ts"] == 0

        deleted, delete_ok = service.delete_subscription(result, "loc-1")
        assert delete_ok is True
        assert deleted["alert_subscriptions"] == []
        assert service.get_subscription(deleted, "loc-1") is None

    def test_add_subscription_prevents_duplicates_and_invalid_operations_fail_cleanly(self):
        service = AlertsSubscriptionService()
        user_data = {
            "alert_subscriptions": [
                {
                    "location_id": "loc-1",
                    "title": "Москва",
                    "label": "Москва",
                    "lat": 55.7558,
                    "lon": 4.1234,
                }
            ]
        }

        unchanged, added = service.add_subscription(
            user_data,
            location_id="another-id",
            title="Москва 2",
            label="Москва",
            lat=55.75584,
            lon=4.12339,
        )
        toggled, toggle_ok = service.toggle_subscription(user_data, "missing")
        updated, update_ok = service.update_interval(user_data, "missing", 5)
        deleted, delete_ok = service.delete_subscription(user_data, "missing")

        assert added is False
        assert len(unchanged["alert_subscriptions"]) == 1
        assert toggle_ok is False
        assert update_ok is False
        assert delete_ok is False
        assert toggled["alert_subscriptions"][0]["location_id"] == "loc-1"
        assert updated["alert_subscriptions"][0]["location_id"] == "loc-1"
        assert deleted["alert_subscriptions"][0]["location_id"] == "loc-1"
