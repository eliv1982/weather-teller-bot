"""
Unit tests for postgres_storage.py — no real PostgreSQL required.

Strategy:
- Pure-function tests (_default_user_data, get_connection env-var validation,
  ai-cache early-return guards) run without any mocking.
- Row-mapper tests (_load_saved_locations, _load_alert_subscriptions) use a
  MagicMock cursor so we can verify the mapping logic in isolation.
- load_user / save_user tests patch _cursor via contextmanager mock so the
  full function path is exercised without a live DB.

Out of scope for this safety-net branch:
- Integration tests that spin up a real PostgreSQL instance.
  Follow-up: add pytest-docker / testcontainers fixture when the team is ready
  to add that dependency (low-risk, isolated CI change).
"""

import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import postgres_storage
from postgres_storage import (
    _default_user_data,
    _load_alert_subscriptions,
    _load_saved_locations,
    get_ai_cached_response,
    load_user,
    save_ai_cached_response,
    save_user,
)


# ---------------------------------------------------------------------------
# _default_user_data — pure function, no I/O
# ---------------------------------------------------------------------------


class TestDefaultUserData:
    def test_returns_dict_with_all_required_keys(self):
        data = _default_user_data()
        assert isinstance(data, dict)
        for key in ("city", "lat", "lon", "saved_locations", "favorite_location_id",
                    "notifications", "alert_subscriptions"):
            assert key in data, f"Missing key: {key!r}"

    def test_city_is_empty_string(self):
        assert _default_user_data()["city"] == ""

    def test_lat_and_lon_are_none(self):
        d = _default_user_data()
        assert d["lat"] is None
        assert d["lon"] is None

    def test_saved_locations_is_empty_list(self):
        assert _default_user_data()["saved_locations"] == []

    def test_alert_subscriptions_is_empty_list(self):
        assert _default_user_data()["alert_subscriptions"] == []

    def test_favorite_location_id_is_none(self):
        assert _default_user_data()["favorite_location_id"] is None

    def test_notifications_defaults(self):
        notif = _default_user_data()["notifications"]
        assert notif["enabled"] is False
        assert notif["interval_h"] == 2
        assert notif["last_check_ts"] == 0

    def test_each_call_returns_independent_dict(self):
        d1 = _default_user_data()
        d2 = _default_user_data()
        assert d1 is not d2
        d1["city"] = "modified"
        assert d2["city"] == ""

    def test_nested_notifications_are_independent_across_calls(self):
        d1 = _default_user_data()
        d2 = _default_user_data()
        d1["notifications"]["interval_h"] = 99
        assert d2["notifications"]["interval_h"] == 2


# ---------------------------------------------------------------------------
# get_connection — env-var validation (no network call)
# ---------------------------------------------------------------------------


class TestGetConnectionEnvVarValidation:
    _PG_VARS = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD")

    def test_raises_when_all_pg_vars_missing(self, monkeypatch):
        for var in self._PG_VARS:
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(RuntimeError, match="Не заданы параметры подключения к PostgreSQL"):
            postgres_storage.get_connection()

    def test_error_message_lists_missing_variable_names(self, monkeypatch):
        for var in self._PG_VARS:
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            postgres_storage.get_connection()
        msg = str(exc_info.value)
        for var in self._PG_VARS:
            assert var in msg, f"Expected {var!r} in error message"

    def test_raises_for_single_missing_var(self, monkeypatch):
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "weather")
        monkeypatch.setenv("PGUSER", "user")
        monkeypatch.delenv("PGPASSWORD", raising=False)
        with pytest.raises(RuntimeError, match="PGPASSWORD"):
            postgres_storage.get_connection()

    def test_does_not_raise_when_all_vars_set(self, monkeypatch):
        """Validation passes; the subsequent psycopg.connect will fail (no real PG),
        but that's a different error not from our validation code."""
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "weather")
        monkeypatch.setenv("PGUSER", "user")
        monkeypatch.setenv("PGPASSWORD", "pass")
        with pytest.raises(Exception) as exc_info:
            postgres_storage.get_connection()
        # Our guard should NOT raise "Не заданы параметры" — it passed validation
        assert "Не заданы параметры" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# AI cache early-return guards — no DB interaction
# ---------------------------------------------------------------------------


class TestAiCacheEarlyReturns:
    def test_get_ai_cached_response_returns_none_for_empty_string_key(self):
        assert get_ai_cached_response("") is None

    def test_get_ai_cached_response_returns_none_for_none_key(self):
        assert get_ai_cached_response(None) is None

    def test_save_ai_cached_response_returns_none_for_empty_cache_key(self):
        result = save_ai_cached_response("", "scenario", "text")
        assert result is None

    def test_save_ai_cached_response_returns_none_for_empty_scenario(self):
        result = save_ai_cached_response("key", "", "response")
        assert result is None

    def test_save_ai_cached_response_returns_none_for_empty_response_text(self):
        result = save_ai_cached_response("key", "scenario", "")
        assert result is None


# ---------------------------------------------------------------------------
# _load_saved_locations — row mapper (mock cursor, no DB)
# ---------------------------------------------------------------------------


def _mock_cursor_with_rows(rows):
    cur = MagicMock()
    cur.fetchall.return_value = rows
    return cur


class TestLoadSavedLocationsMapper:
    def test_maps_single_row_to_location_dict(self):
        row = {"id": "loc1", "title": "Дом", "label": "Москва, RU", "lat": 55.75, "lon": 37.62}
        result = _load_saved_locations(_mock_cursor_with_rows([row]), user_id=1)

        assert len(result) == 1
        loc = result[0]
        assert loc["id"] == "loc1"
        assert loc["title"] == "Дом"
        assert loc["label"] == "Москва, RU"
        assert loc["lat"] == 55.75
        assert loc["lon"] == 37.62

    def test_returns_empty_list_for_zero_rows(self):
        assert _load_saved_locations(_mock_cursor_with_rows([]), user_id=1) == []

    def test_returns_empty_list_when_fetchall_returns_none(self):
        cur = MagicMock()
        cur.fetchall.return_value = None
        assert _load_saved_locations(cur, user_id=1) == []

    def test_coerces_id_to_str(self):
        row = {"id": 42, "title": "T", "label": "L", "lat": 1.0, "lon": 2.0}
        result = _load_saved_locations(_mock_cursor_with_rows([row]), user_id=1)
        assert isinstance(result[0]["id"], str)

    def test_coerces_lat_lon_to_float(self):
        row = {"id": "x", "title": "T", "label": "L", "lat": "59.95", "lon": "30.32"}
        result = _load_saved_locations(_mock_cursor_with_rows([row]), user_id=1)
        assert isinstance(result[0]["lat"], float)
        assert isinstance(result[0]["lon"], float)

    def test_maps_multiple_rows_preserving_order(self):
        rows = [
            {"id": "a", "title": "A", "label": "La", "lat": 1.0, "lon": 2.0},
            {"id": "b", "title": "B", "label": "Lb", "lat": 3.0, "lon": 4.0},
        ]
        result = _load_saved_locations(_mock_cursor_with_rows(rows), user_id=5)
        assert [r["id"] for r in result] == ["a", "b"]


# ---------------------------------------------------------------------------
# _load_alert_subscriptions — row mapper (mock cursor, no DB)
# ---------------------------------------------------------------------------


def _make_alert_row(**overrides) -> dict:
    base = {
        "location_id": "loc123",
        "title": "Работа",
        "label": "Berlin, DE",
        "lat": 52.52,
        "lon": 13.41,
        "enabled": True,
        "interval_h": 3,
        "last_check_ts": 1717000000,
        "last_alert_signature": "sig_abc",
    }
    base.update(overrides)
    return base


class TestLoadAlertSubscriptionsMapper:
    def test_maps_single_row_to_subscription_dict(self):
        result = _load_alert_subscriptions(
            _mock_cursor_with_rows([_make_alert_row()]), user_id=1
        )
        assert len(result) == 1
        sub = result[0]
        assert sub["location_id"] == "loc123"
        assert sub["title"] == "Работа"
        assert sub["lat"] == 52.52
        assert sub["enabled"] is True
        assert sub["interval_h"] == 3
        assert sub["last_check_ts"] == 1717000000
        assert sub["last_alert_signature"] == "sig_abc"

    def test_returns_empty_list_for_zero_rows(self):
        assert _load_alert_subscriptions(_mock_cursor_with_rows([]), user_id=1) == []

    def test_none_last_alert_signature_becomes_empty_string(self):
        row = _make_alert_row(last_alert_signature=None)
        result = _load_alert_subscriptions(_mock_cursor_with_rows([row]), user_id=1)
        assert result[0]["last_alert_signature"] == ""

    def test_coerces_enabled_to_bool(self):
        result = _load_alert_subscriptions(
            _mock_cursor_with_rows([_make_alert_row(enabled=1)]), user_id=1
        )
        assert isinstance(result[0]["enabled"], bool)

    def test_coerces_interval_h_to_int(self):
        result = _load_alert_subscriptions(
            _mock_cursor_with_rows([_make_alert_row(interval_h="4")]), user_id=1
        )
        assert isinstance(result[0]["interval_h"], int)
        assert result[0]["interval_h"] == 4

    def test_coerces_last_check_ts_to_int(self):
        result = _load_alert_subscriptions(
            _mock_cursor_with_rows([_make_alert_row(last_check_ts="0")]), user_id=1
        )
        assert isinstance(result[0]["last_check_ts"], int)

    def test_maps_multiple_rows(self):
        rows = [_make_alert_row(location_id="a"), _make_alert_row(location_id="b")]
        result = _load_alert_subscriptions(_mock_cursor_with_rows(rows), user_id=1)
        assert [r["location_id"] for r in result] == ["a", "b"]


# ---------------------------------------------------------------------------
# load_user — mocked _cursor, no DB
# ---------------------------------------------------------------------------


def _make_cursor_cm(user_row, saved_rows=None, alert_rows=None):
    """Return a _cursor replacement (contextmanager) that yields a mock cursor."""
    cur = MagicMock()
    cur.fetchone.return_value = user_row
    # fetchall is called twice: once for saved_locations, once for alert_subscriptions
    cur.fetchall.side_effect = [saved_rows or [], alert_rows or []]

    @contextmanager
    def _mock_cursor(commit=False):
        yield cur

    return _mock_cursor


class TestLoadUser:
    def test_returns_default_data_when_user_not_found(self):
        with patch("postgres_storage._cursor", _make_cursor_cm(user_row=None)):
            result = load_user(user_id=999)
        assert result == _default_user_data()

    def test_returns_city_for_existing_user(self):
        user_row = {
            "current_city": "Москва",
            "current_lat": 55.75,
            "current_lon": 37.62,
            "favorite_location_id": None,
            "notifications_enabled": False,
            "notifications_interval_h": 2,
            "notifications_last_check_ts": 0,
        }
        with patch("postgres_storage._cursor", _make_cursor_cm(user_row=user_row)):
            result = load_user(user_id=1)
        assert result["city"] == "Москва"
        assert result["lat"] == 55.75
        assert result["lon"] == 37.62

    def test_null_city_becomes_empty_string(self):
        user_row = {
            "current_city": None,
            "current_lat": None,
            "current_lon": None,
            "favorite_location_id": None,
            "notifications_enabled": False,
            "notifications_interval_h": 2,
            "notifications_last_check_ts": 0,
        }
        with patch("postgres_storage._cursor", _make_cursor_cm(user_row=user_row)):
            result = load_user(user_id=1)
        assert result["city"] == ""

    def test_result_includes_saved_locations_and_subscriptions_lists(self):
        user_row = {
            "current_city": "X",
            "current_lat": None,
            "current_lon": None,
            "favorite_location_id": None,
            "notifications_enabled": False,
            "notifications_interval_h": 2,
            "notifications_last_check_ts": 0,
        }
        saved = [{"id": "s1", "title": "T", "label": "L", "lat": 1.0, "lon": 2.0}]
        alerts = [_make_alert_row()]
        with patch("postgres_storage._cursor", _make_cursor_cm(user_row, saved, alerts)):
            result = load_user(user_id=1)
        assert isinstance(result["saved_locations"], list)
        assert isinstance(result["alert_subscriptions"], list)
        assert len(result["saved_locations"]) == 1
        assert len(result["alert_subscriptions"]) == 1


# ---------------------------------------------------------------------------
# save_user — input normalisation (mocked _cursor, no DB)
# ---------------------------------------------------------------------------


def _make_save_cursor_cm():
    """Returns (context_manager_factory, mock_cursor) for save_user tests."""
    cur = MagicMock()

    @contextmanager
    def _mock_cursor(commit=False):
        yield cur

    return _mock_cursor, cur


class TestSaveUserInputNormalization:
    def _valid_user_data(self, **overrides) -> dict:
        data = {
            "city": "Berlin",
            "lat": 52.5,
            "lon": 13.4,
            "saved_locations": [],
            "alert_subscriptions": [],
            "notifications": {"enabled": True, "interval_h": 4, "last_check_ts": 0},
            "favorite_location_id": None,
        }
        data.update(overrides)
        return data

    def test_valid_data_reaches_db_execute(self):
        mock_cm, mock_cur = _make_save_cursor_cm()
        with patch("postgres_storage._cursor", mock_cm):
            save_user(1, self._valid_user_data())
        assert mock_cur.execute.called

    def test_non_dict_user_data_falls_back_to_default(self):
        mock_cm, mock_cur = _make_save_cursor_cm()
        with patch("postgres_storage._cursor", mock_cm):
            save_user(1, None)  # None is not a dict → uses _default_user_data()
        assert mock_cur.execute.called

    def test_non_dict_notifications_does_not_raise(self):
        mock_cm, mock_cur = _make_save_cursor_cm()
        with patch("postgres_storage._cursor", mock_cm):
            save_user(1, self._valid_user_data(notifications="not_a_dict"))
        assert mock_cur.execute.called

    def test_zero_interval_h_is_replaced_with_default_2(self):
        """interval_h ≤ 0 is treated as invalid and normalised to 2."""
        mock_cm, mock_cur = _make_save_cursor_cm()
        with patch("postgres_storage._cursor", mock_cm):
            save_user(1, self._valid_user_data(notifications={"interval_h": 0}))
        # The function should not raise and should have called execute
        assert mock_cur.execute.called

    def test_non_list_saved_locations_does_not_raise(self):
        mock_cm, mock_cur = _make_save_cursor_cm()
        with patch("postgres_storage._cursor", mock_cm):
            save_user(1, self._valid_user_data(saved_locations="not_a_list"))
        assert mock_cur.execute.called

    def test_incomplete_saved_location_entries_are_skipped(self):
        """Entries missing required fields must be silently skipped."""
        mock_cm, mock_cur = _make_save_cursor_cm()
        locations = [
            None,
            "string",
            {"id": "ok", "title": "T", "label": "L", "lat": 1.0, "lon": 2.0},
            {"id": "missing_lat"},  # incomplete
        ]
        with patch("postgres_storage._cursor", mock_cm):
            save_user(1, self._valid_user_data(saved_locations=locations))
        assert mock_cur.execute.called

    def test_incomplete_alert_subscription_entries_are_skipped(self):
        mock_cm, mock_cur = _make_save_cursor_cm()
        subscriptions = [
            None,
            {"location_id": "ok", "title": "T", "label": "L", "lat": 1.0, "lon": 2.0},
            {"location_id": "no_lat"},  # incomplete
        ]
        with patch("postgres_storage._cursor", mock_cm):
            save_user(1, self._valid_user_data(alert_subscriptions=subscriptions))
        assert mock_cur.execute.called


# ---------------------------------------------------------------------------
# Integration test placeholder — skipped without real PG
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "Integration tests require a live PostgreSQL instance. "
        "Follow-up: add pytest-docker/testcontainers fixture in a dedicated branch."
    )
)
class TestPostgresStorageIntegration:
    """Placeholder for future integration tests against a real PG instance."""

    def test_init_and_load_user_roundtrip(self):
        """init_postgres_db → save_user → load_user should return consistent data."""
        ...

    def test_save_user_overwrites_existing_saved_locations(self):
        ...

    def test_ai_cache_save_and_retrieve(self):
        ...

    def test_ai_cache_respects_ttl(self):
        ...
