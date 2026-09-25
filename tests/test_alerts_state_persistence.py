"""
The alerts worker works on a stale snapshot (load_all_users at the start of an iteration) while the bot
keeps editing the same user. Its state write must touch only the worker-owned columns of the one
subscription it checked, so concurrent same-user edits are never lost.

These tests run the *real* postgres_storage functions and the *real* worker against an in-memory SQLite
database behind the ``_cursor`` seam (the SQL used is portable), so the actual UPDATE/DELETE/INSERT
semantics are exercised without a PostgreSQL server. Concurrent bot edits use the same
load_user -> mutate -> save_user round trip as the bot handlers.
"""

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import postgres_storage
from alerts_service import ensure_notifications_defaults
from alerts_subscription_service import AlertsSubscriptionService
from workers.alerts_worker import run_alerts_worker_iteration

NOW = 1700000000
ALERT = {"text": "15:00 — сильный дождь", "slot_ts_utc": 1700003600, "description": "сильный дождь"}
MOSCOW = (55.75, 37.61)
PETERSBURG = (59.93, 30.33)
SIGNATURE_LOC_1 = "loc-1|1700003600|15:00 — сильный дождь"

# Same tables/columns/keys as postgres_storage.init_postgres_db (which uses PostgreSQL-only DDL).
SCHEMA = """
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    current_city TEXT NULL,
    current_lat DOUBLE PRECISION NULL,
    current_lon DOUBLE PRECISION NULL,
    favorite_location_id TEXT NULL,
    notifications_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    notifications_interval_h INTEGER NOT NULL DEFAULT 2,
    notifications_last_check_ts BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE saved_locations (
    id TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    label TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, id)
);
CREATE TABLE alert_subscriptions (
    location_id TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    label TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    interval_h INTEGER NOT NULL DEFAULT 2,
    last_check_ts BIGINT NOT NULL DEFAULT 0,
    last_alert_signature TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, location_id)
);
"""


class _DictCursor:
    """psycopg-like cursor over sqlite: %s placeholders, dict rows, rowcount."""

    def __init__(self, conn: sqlite3.Connection):
        self._cur = conn.cursor()

    def execute(self, sql, params=()):
        self._cur.execute(sql.replace("%s", "?"), tuple(params or ()))
        return self

    def _as_dict(self, row):
        if row is None:
            return None
        return {column[0]: value for column, value in zip(self._cur.description, row)}

    def fetchone(self):
        return self._as_dict(self._cur.fetchone())

    def fetchall(self):
        return [self._as_dict(row) for row in self._cur.fetchall()]

    @property
    def rowcount(self):
        return self._cur.rowcount


@pytest.fixture
def db(monkeypatch) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)

    @contextmanager
    def _fake_cursor(commit: bool = False):
        try:
            yield _DictCursor(conn)
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise

    monkeypatch.setattr(postgres_storage, "_cursor", _fake_cursor)
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: NOW)
    yield conn
    conn.close()


def _location(location_id: str, title: str, coords: tuple[float, float]) -> dict:
    return {"id": location_id, "title": title, "label": f"{title}, Россия", "lat": coords[0], "lon": coords[1]}


def _subscription(location_id: str, coords: tuple[float, float], *, interval_h=2, last_check_ts=0, signature="") -> dict:
    return {
        "location_id": location_id,
        "title": f"title-{location_id}",
        "label": f"label-{location_id}",
        "lat": coords[0],
        "lon": coords[1],
        "enabled": True,
        "interval_h": interval_h,
        "last_check_ts": last_check_ts,
        "last_alert_signature": signature,
    }


def _seed_user(user_id: int, *, saved_locations, subscriptions, favorite=None, city="Москва") -> None:
    postgres_storage.save_user(
        user_id,
        {
            "city": city,
            "lat": MOSCOW[0],
            "lon": MOSCOW[1],
            "saved_locations": saved_locations,
            "favorite_location_id": favorite,
            "notifications": {"enabled": True, "interval_h": 2, "last_check_ts": 0},
            "alert_subscriptions": subscriptions,
        },
    )


def _bot_edit(user_id: int, mutate) -> None:
    """A bot handler: load the user, change something, save the whole user back."""
    user_data = postgres_storage.load_user(user_id)
    mutate(user_data)
    postgres_storage.save_user(user_id, user_data)


def _subs_by_id(user_id: int) -> dict[str, dict]:
    return {sub["location_id"]: sub for sub in postgres_storage.load_user(user_id)["alert_subscriptions"]}


def _locations_by_id(user_id: int) -> dict[str, dict]:
    return {loc["id"]: loc for loc in postgres_storage.load_user(user_id)["saved_locations"]}


class _Bot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


def _forbid_full_snapshot_write(*args, **kwargs):
    raise AssertionError("the worker must not write a user snapshot")


def _worker_ctx(*, bot, during_first_forecast=None):
    """Real storage + real subscription service; only the network/AI collaborators are stubbed."""
    hooks = [during_first_forecast] if during_first_forecast else []

    def get_forecast(lat, lon):
        if hooks:
            hooks.pop()()  # the user edits data through the bot while the worker holds its snapshot
        return [{"dt": 1700003600, "lat": lat}]

    return SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(
            info=lambda *a, **k: None, warning=lambda *a, **k: None, exception=lambda *a, **k: None
        ),
        load_all_users=postgres_storage.load_all_users,
        save_user=_forbid_full_snapshot_write,
        save_all_users=_forbid_full_snapshot_write,
        update_alert_subscription_state=postgres_storage.update_alert_subscription_state,
        alerts_subscription_service=AlertsSubscriptionService(),
        ensure_notifications_defaults=ensure_notifications_defaults,
        get_forecast_5d3h=get_forecast,
        detect_weather_alerts=lambda items, now_ts, horizon_hours: [ALERT] if items[0]["lat"] == MOSCOW[0] else [],
        ai_weather_service=SimpleNamespace(explain_weather_alert=lambda label, payload: ""),
    )


# --- the race, end to end ---------------------------------------------------------------------


def test_worker_state_update_preserves_concurrent_same_user_edits(db):
    home = _location("home", "Дом", MOSCOW)
    work = _location("work", "Работа", PETERSBURG)
    _seed_user(
        7,
        saved_locations=[home, work],
        favorite="home",
        subscriptions=[
            _subscription("loc-1", MOSCOW, last_check_ts=0),  # due, has an alert
            _subscription("loc-2", PETERSBURG, interval_h=4, last_check_ts=NOW - 10 * 3600),  # due, no alert
        ],
    )
    service = AlertsSubscriptionService()
    dacha = _location("dacha", "Дача", (56.0, 38.0))
    new_subscription = _subscription("loc-3", (48.85, 2.35))

    def concurrent_bot_edits():
        def mutate(user_data):
            user_data["city"] = "Санкт-Петербург"
            user_data["favorite_location_id"] = "dacha"
            user_data["saved_locations"] = [home, {**work, "title": "Офис-2"}, dacha]
            service.update_interval(user_data, "loc-2", 1)  # bot behaviour: new interval + last_check_ts=0
            user_data["alert_subscriptions"].append(new_subscription)

        _bot_edit(7, mutate)

    bot = _Bot()
    changed = run_alerts_worker_iteration(ctx=_worker_ctx(bot=bot, during_first_forecast=concurrent_bot_edits))

    assert changed is True
    final = postgres_storage.load_user(7)
    # Unrelated user data written by the bot while the worker was running survived.
    assert final["city"] == "Санкт-Петербург"
    assert final["favorite_location_id"] == "dacha"
    assert {loc_id: loc["title"] for loc_id, loc in _locations_by_id(7).items()} == {
        "home": "Дом",
        "work": "Офис-2",
        "dacha": "Дача",
    }
    subs = _subs_by_id(7)
    assert set(subs) == {"loc-1", "loc-2", "loc-3"}  # the subscription added meanwhile is not deleted
    # The worker's own result was recorded for the subscription it alerted on...
    assert subs["loc-1"]["last_check_ts"] == NOW
    assert subs["loc-1"]["last_alert_signature"] == SIGNATURE_LOC_1
    assert bot.messages and bot.messages[0][0] == 7 and len(bot.messages) == 1
    # ...while the user's interval change and its "check again now" reset were kept.
    assert subs["loc-2"]["interval_h"] == 1
    assert subs["loc-2"]["last_check_ts"] == 0
    assert subs["loc-3"] == {**new_subscription, "last_alert_signature": ""}


def test_worker_state_update_does_not_resurrect_subscription_deleted_meanwhile(db):
    home = _location("home", "Дом", MOSCOW)
    _seed_user(
        7,
        saved_locations=[home],
        subscriptions=[_subscription("loc-1", MOSCOW), _subscription("loc-2", PETERSBURG)],
    )
    service = AlertsSubscriptionService()

    def concurrent_bot_edits():
        _bot_edit(7, lambda user_data: service.delete_subscription(user_data, "loc-1"))

    changed = run_alerts_worker_iteration(ctx=_worker_ctx(bot=_Bot(), during_first_forecast=concurrent_bot_edits))

    assert changed is True
    subs = _subs_by_id(7)
    assert set(subs) == {"loc-2"}
    assert subs["loc-2"]["last_check_ts"] == NOW
    assert set(_locations_by_id(7)) == {"home"}


def test_worker_keeps_duplicate_coordinate_subscriptions_that_ensure_defaults_drops_in_memory(db):
    # ensure_defaults dedups by rounded coordinates in the worker's in-memory copy. Writing that copy back
    # (the old save_user path) would silently DELETE the "duplicate" row; a narrow update must not.
    _seed_user(
        7,
        saved_locations=[],
        subscriptions=[_subscription("loc-1", MOSCOW), _subscription("loc-dup", (MOSCOW[0] + 0.00001, MOSCOW[1]))],
    )

    run_alerts_worker_iteration(ctx=_worker_ctx(bot=_Bot()))

    subs = _subs_by_id(7)
    assert set(subs) == {"loc-1", "loc-dup"}
    assert subs["loc-1"]["last_check_ts"] == NOW
    assert subs["loc-dup"]["last_check_ts"] == 0


def test_worker_does_not_touch_other_users(db):
    for user_id in (7, 8):
        _seed_user(
            user_id,
            saved_locations=[_location("home", "Дом", MOSCOW)],
            subscriptions=[_subscription("loc-1", MOSCOW, last_check_ts=0 if user_id == 7 else NOW - 60)],
        )
    before_user_8 = postgres_storage.load_user(8)
    edited_user_8 = {}

    def concurrent_edit_of_other_user():
        _bot_edit(8, lambda user_data: user_data.update(city="Казань"))
        edited_user_8.update(postgres_storage.load_user(8))

    run_alerts_worker_iteration(ctx=_worker_ctx(bot=_Bot(), during_first_forecast=concurrent_edit_of_other_user))

    assert edited_user_8["city"] == "Казань"
    assert postgres_storage.load_user(8) == edited_user_8  # not checked (not due) and not written by the worker
    assert postgres_storage.load_user(8)["alert_subscriptions"] == before_user_8["alert_subscriptions"]
    assert _subs_by_id(7)["loc-1"]["last_check_ts"] == NOW


def test_control_writing_the_stale_snapshot_back_does_lose_concurrent_edits(db):
    """Control: proves this harness detects the race the narrow update exists to prevent."""
    _seed_user(7, saved_locations=[_location("home", "Дом", MOSCOW)], subscriptions=[_subscription("loc-1", MOSCOW)])
    stale_snapshot = postgres_storage.load_all_users()[7]  # what the worker holds during its iteration

    _bot_edit(7, lambda user_data: user_data["saved_locations"].append(_location("dacha", "Дача", (56.0, 38.0))))
    stale_snapshot["alert_subscriptions"][0]["last_check_ts"] = NOW
    postgres_storage.save_user(7, stale_snapshot)  # the old worker behaviour

    assert set(_locations_by_id(7)) == {"home"}  # the concurrent "dacha" edit was overwritten


# --- the interval-change race: last_check_ts alone cannot tell the user's reset from the snapshot ------


def test_worker_does_not_overwrite_interval_change_reset_when_snapshot_check_ts_was_already_zero(db):
    """
    Final-review case. Worker snapshot: interval_h=2, last_check_ts=0. While it processes the subscription the
    user sets interval 1; the bot stores interval_h=1 and resets last_check_ts to 0 - the very value the
    snapshot already held, so a compare-and-set on last_check_ts alone passes and the worker's timestamp would
    delay the user's "check again right away" by a full interval.
    """
    _seed_user(7, saved_locations=[], subscriptions=[_subscription("loc-1", MOSCOW, interval_h=2, last_check_ts=0)])
    service = AlertsSubscriptionService()

    def concurrent_interval_change():
        _bot_edit(7, lambda user_data: service.update_interval(user_data, "loc-1", 1))

    bot = _Bot()
    changed = run_alerts_worker_iteration(ctx=_worker_ctx(bot=bot, during_first_forecast=concurrent_interval_change))

    assert changed is True
    sub = _subs_by_id(7)["loc-1"]
    assert sub["interval_h"] == 1
    assert sub["last_check_ts"] == 0  # the user's reset survived; NOW would mean the worker overwrote it
    assert sub["last_alert_signature"] == SIGNATURE_LOC_1  # the alert that was really sent is still remembered
    assert [chat_id for chat_id, _ in bot.messages] == [7]


def test_worker_persists_check_timestamp_and_signature_when_nothing_changed_concurrently(db):
    _seed_user(
        7,
        saved_locations=[],
        subscriptions=[
            _subscription("loc-1", MOSCOW, interval_h=4, last_check_ts=NOW - 5 * 3600, signature="old"),  # due, alert
            _subscription("loc-2", PETERSBURG, interval_h=1, last_check_ts=0),  # due, no alert
        ],
    )
    bot = _Bot()

    changed = run_alerts_worker_iteration(ctx=_worker_ctx(bot=bot))

    assert changed is True
    subs = _subs_by_id(7)
    assert (subs["loc-1"]["interval_h"], subs["loc-1"]["last_check_ts"]) == (4, NOW)
    assert subs["loc-1"]["last_alert_signature"] == SIGNATURE_LOC_1
    assert (subs["loc-2"]["interval_h"], subs["loc-2"]["last_check_ts"]) == (1, NOW)
    assert subs["loc-2"]["last_alert_signature"] == ""
    assert [chat_id for chat_id, _ in bot.messages] == [7]


# --- update_alert_subscription_state itself ---------------------------------------------------


def _row(conn: sqlite3.Connection, user_id: int, location_id: str) -> dict | None:
    cur = conn.execute("SELECT * FROM alert_subscriptions WHERE user_id = ? AND location_id = ?", (user_id, location_id))
    row = cur.fetchone()
    return None if row is None else {column[0]: value for column, value in zip(cur.description, row)}


def test_update_touches_only_the_two_worker_owned_columns(db):
    _seed_user(7, saved_locations=[], subscriptions=[_subscription("loc-1", MOSCOW, interval_h=3, signature="old")])
    before = _row(db, 7, "loc-1")

    found = postgres_storage.update_alert_subscription_state(
        7, "loc-1", last_check_ts=NOW, expected_last_check_ts=0, expected_interval_h=3, last_alert_signature="new"
    )

    after = _row(db, 7, "loc-1")
    assert found is True
    assert {column for column in before if before[column] != after[column]} == {"last_check_ts", "last_alert_signature"}
    assert (after["last_check_ts"], after["last_alert_signature"]) == (NOW, "new")


def test_update_without_signature_keeps_the_stored_signature(db):
    _seed_user(7, saved_locations=[], subscriptions=[_subscription("loc-1", MOSCOW, signature="keep-me")])

    postgres_storage.update_alert_subscription_state(
        7, "loc-1", last_check_ts=NOW, expected_last_check_ts=0, expected_interval_h=2
    )

    row = _row(db, 7, "loc-1")
    assert (row["last_check_ts"], row["last_alert_signature"]) == (NOW, "keep-me")


def test_update_does_not_overwrite_a_check_timestamp_changed_since_the_snapshot(db):
    _seed_user(7, saved_locations=[], subscriptions=[_subscription("loc-1", MOSCOW, last_check_ts=0)])

    found = postgres_storage.update_alert_subscription_state(
        7,
        "loc-1",
        last_check_ts=NOW,
        expected_last_check_ts=NOW - 7200,
        expected_interval_h=2,  # unchanged: the timestamp mismatch alone must be enough to keep the stored value
        last_alert_signature="sent",
    )

    row = _row(db, 7, "loc-1")
    assert found is True
    assert row["last_check_ts"] == 0  # the user's reset wins...
    assert row["last_alert_signature"] == "sent"  # ...but an alert that was actually sent is never forgotten


def test_update_applies_the_check_timestamp_when_timestamp_and_interval_both_match_the_snapshot(db):
    checked_at = NOW - 5 * 3600
    _seed_user(
        7, saved_locations=[], subscriptions=[_subscription("loc-1", MOSCOW, interval_h=4, last_check_ts=checked_at)]
    )

    found = postgres_storage.update_alert_subscription_state(
        7,
        "loc-1",
        last_check_ts=NOW,
        expected_last_check_ts=checked_at,
        expected_interval_h=4,
        last_alert_signature="sent",
    )

    row = _row(db, 7, "loc-1")
    assert found is True
    assert (row["last_check_ts"], row["interval_h"], row["last_alert_signature"]) == (NOW, 4, "sent")


def test_update_does_not_overwrite_a_reset_when_only_the_interval_changed_since_the_snapshot(db):
    # Stored state after the user's interval change: interval 1, last_check_ts reset to 0.
    # The worker's snapshot had interval 2 and last_check_ts already 0: the timestamp matches, the interval does not.
    _seed_user(7, saved_locations=[], subscriptions=[_subscription("loc-1", MOSCOW, interval_h=1, last_check_ts=0)])

    found = postgres_storage.update_alert_subscription_state(
        7, "loc-1", last_check_ts=NOW, expected_last_check_ts=0, expected_interval_h=2, last_alert_signature="sent"
    )

    row = _row(db, 7, "loc-1")
    assert found is True
    assert (row["interval_h"], row["last_check_ts"]) == (1, 0)
    assert row["last_alert_signature"] == "sent"  # signature persistence is independent of the timestamp condition


def test_update_without_signature_keeps_the_stored_one_when_the_interval_changed(db):
    _seed_user(7, saved_locations=[], subscriptions=[_subscription("loc-1", MOSCOW, interval_h=1, signature="keep-me")])

    postgres_storage.update_alert_subscription_state(
        7, "loc-1", last_check_ts=NOW, expected_last_check_ts=0, expected_interval_h=2
    )

    row = _row(db, 7, "loc-1")
    assert (row["interval_h"], row["last_check_ts"], row["last_alert_signature"]) == (1, 0, "keep-me")


def test_update_of_missing_subscription_creates_nothing(db):
    _seed_user(7, saved_locations=[], subscriptions=[_subscription("loc-1", MOSCOW)])

    unknown_subscription = postgres_storage.update_alert_subscription_state(
        7, "nope", last_check_ts=NOW, expected_last_check_ts=0, expected_interval_h=2, last_alert_signature="x"
    )
    unknown_user = postgres_storage.update_alert_subscription_state(
        99, "loc-1", last_check_ts=NOW, expected_last_check_ts=0, expected_interval_h=2, last_alert_signature="x"
    )

    assert (unknown_subscription, unknown_user) == (False, False)
    assert db.execute("SELECT COUNT(*) FROM alert_subscriptions").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_update_is_isolated_per_user_even_with_the_same_location_id(db):
    for user_id in (7, 8):
        _seed_user(user_id, saved_locations=[], subscriptions=[_subscription("loc-1", MOSCOW)])
    before_user_8 = _row(db, 8, "loc-1")

    postgres_storage.update_alert_subscription_state(
        7,
        "loc-1",
        last_check_ts=NOW,
        expected_last_check_ts=0,
        expected_interval_h=2,
        last_alert_signature="only-for-7",
    )

    assert _row(db, 8, "loc-1") == before_user_8
    assert _row(db, 7, "loc-1")["last_alert_signature"] == "only-for-7"


def test_update_does_not_touch_users_or_saved_locations_tables(db):
    _seed_user(
        7,
        saved_locations=[_location("home", "Дом", MOSCOW)],
        subscriptions=[_subscription("loc-1", MOSCOW)],
    )
    tables_before = {
        table: db.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall() for table in ("users", "saved_locations")
    }

    postgres_storage.update_alert_subscription_state(
        7, "loc-1", last_check_ts=NOW, expected_last_check_ts=0, expected_interval_h=2, last_alert_signature="s"
    )

    tables_after = {
        table: db.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall() for table in ("users", "saved_locations")
    }
    assert tables_after == tables_before
