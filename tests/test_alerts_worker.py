from types import SimpleNamespace

from workers.alerts_worker import run_alerts_worker_iteration


class _Bot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append({"chat_id": chat_id, "text": text})


class _AlertsSubscriptionService:
    def ensure_defaults(self, user_data):
        return user_data

    def list_subscriptions(self, user_data):
        return user_data.get("alert_subscriptions", [])


def _forbid_full_snapshot_write(*args, **kwargs):
    raise AssertionError("worker must not write a user snapshot; it may only call update_alert_subscription_state")


def _sub(location_id="loc-1", *, last_check_ts=0, last_alert_signature="", enabled=True):
    return {
        "location_id": location_id,
        "label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "enabled": enabled,
        "interval_h": 2,
        "last_check_ts": last_check_ts,
        "last_alert_signature": last_alert_signature,
    }


def _worker_ctx(*, all_users, updates, bot=None, alerts=None, forecast_items=None, update_state=None, logger=None):
    """Worker ctx where every collaborator is a stub; `updates` records (user_id, location_id, kwargs)."""
    forecast_items = [{"dt": 1700003600}] if forecast_items is None else forecast_items
    return SimpleNamespace(
        bot=bot or _Bot(),
        logger=logger
        or SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            exception=lambda *args, **kwargs: None,
        ),
        load_all_users=lambda: all_users,
        save_user=_forbid_full_snapshot_write,
        save_all_users=_forbid_full_snapshot_write,
        update_alert_subscription_state=update_state
        or (lambda user_id, location_id, **kwargs: updates.append((user_id, location_id, kwargs)) or True),
        alerts_subscription_service=_AlertsSubscriptionService(),
        ensure_notifications_defaults=lambda user_data: user_data,
        get_forecast_5d3h=lambda lat, lon: forecast_items,
        detect_weather_alerts=lambda forecast_items, now_ts, horizon_hours: alerts or [],
        ai_weather_service=SimpleNamespace(explain_weather_alert=lambda location_label, payload: ""),
    )


def test_run_alerts_worker_iteration_sends_alert_and_persists_signature(monkeypatch):
    bot = _Bot()
    updates = []
    all_users = {
        "7": {
            "alert_subscriptions": [
                {
                    "location_id": "loc-1",
                    "label": "Россия — Москва (Россия, Москва)",
                    "lat": 55.75,
                    "lon": 37.61,
                    "enabled": True,
                    "interval_h": 2,
                    "last_check_ts": 0,
                    "last_alert_signature": "",
                }
            ]
        }
    }
    forecast_items = [
        {
            "dt": 1700003600,
            "main": {"temp": 10.0, "feels_like": 6.5},
            "wind": {"speed": 5.0},
            "pop": 0.8,
        }
    ]
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            exception=lambda *args, **kwargs: None,
        ),
        load_all_users=lambda: all_users,
        save_user=_forbid_full_snapshot_write,
        save_all_users=_forbid_full_snapshot_write,
        update_alert_subscription_state=lambda user_id, location_id, **kwargs: updates.append(
            (user_id, location_id, kwargs)
        ),
        alerts_subscription_service=_AlertsSubscriptionService(),
        ensure_notifications_defaults=lambda user_data: user_data,
        get_forecast_5d3h=lambda lat, lon: forecast_items,
        detect_weather_alerts=lambda forecast_items, now_ts, horizon_hours: [
            {
                "text": "15:00 — сильный дождь",
                "slot_ts_utc": 1700003600,
                "description": "сильный дождь",
            }
        ],
        ai_weather_service=SimpleNamespace(
            explain_weather_alert=lambda location_label, payload: f"Возьми зонт для {location_label}"
        ),
    )

    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: 1700000000)

    changed = run_alerts_worker_iteration(ctx=ctx)

    assert changed is True
    assert updates == [
        (
            7,
            "loc-1",
            {
                "last_check_ts": 1700000000,
                "expected_last_check_ts": 0,
                "expected_interval_h": 2,
                "last_alert_signature": "loc-1|1700003600|15:00 — сильный дождь",
            },
        )
    ]
    sub = all_users["7"]["alert_subscriptions"][0]
    assert sub["last_check_ts"] == 1700000000
    assert sub["last_alert_signature"] == "loc-1|1700003600|15:00 — сильный дождь"
    assert bot.messages == [
        {
            "chat_id": 7,
            "text": (
                "🌤 Weather Teller\n"
                "Для локации Москва найдено изменение погоды:\n"
                "• 15:00 — сильный дождь\n\n"
                "🪄 Совет:\n"
                "Возьми зонт для Москва"
            ),
        }
    ]


def test_run_alerts_worker_iteration_skips_duplicate_alert_signature(monkeypatch):
    bot = _Bot()
    updates = []
    all_users = {
        "7": {
            "alert_subscriptions": [
                {
                    "location_id": "loc-1",
                    "label": "Москва",
                    "lat": 55.75,
                    "lon": 37.61,
                    "enabled": True,
                    "interval_h": 2,
                    "last_check_ts": 0,
                    "last_alert_signature": "loc-1|1700003600|15:00 — сильный дождь",
                }
            ]
        }
    }
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            exception=lambda *args, **kwargs: None,
        ),
        load_all_users=lambda: all_users,
        save_user=_forbid_full_snapshot_write,
        save_all_users=_forbid_full_snapshot_write,
        update_alert_subscription_state=lambda user_id, location_id, **kwargs: updates.append(
            (user_id, location_id, kwargs)
        ),
        alerts_subscription_service=_AlertsSubscriptionService(),
        ensure_notifications_defaults=lambda user_data: user_data,
        get_forecast_5d3h=lambda lat, lon: [{"dt": 1700003600}],
        detect_weather_alerts=lambda forecast_items, now_ts, horizon_hours: [
            {
                "text": "15:00 — сильный дождь",
                "slot_ts_utc": 1700003600,
                "description": "сильный дождь",
            }
        ],
        ai_weather_service=SimpleNamespace(
            explain_weather_alert=lambda location_label, payload: "unused"
        ),
    )

    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: 1700000000)

    changed = run_alerts_worker_iteration(ctx=ctx)

    assert changed is True
    # Same signature: only the check timestamp moves; the stored signature is left untouched (None = keep).
    assert updates == [
        (7, "loc-1", {"last_check_ts": 1700000000, "expected_last_check_ts": 0, "expected_interval_h": 2, "last_alert_signature": None})
    ]
    assert all_users["7"]["alert_subscriptions"][0]["last_check_ts"] == 1700000000
    assert bot.messages == []


_ALERT = {"text": "15:00 — сильный дождь", "slot_ts_utc": 1700003600, "description": "сильный дождь"}
_SIGNATURE = "loc-1|1700003600|15:00 — сильный дождь"
_NOW = 1700000000


def test_run_alerts_worker_iteration_updates_only_due_subscriptions(monkeypatch):
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: _NOW)
    all_users = {
        "7": {"alert_subscriptions": [_sub("loc-1", last_check_ts=0), _sub("loc-2", last_check_ts=_NOW - 60)]},
        "8": {"alert_subscriptions": [_sub("loc-3", last_check_ts=_NOW - 60)]},  # checked a minute ago -> not due
    }
    snapshot_of_user_8 = {"alert_subscriptions": [dict(all_users["8"]["alert_subscriptions"][0])]}
    updates = []
    bot = _Bot()
    ctx = _worker_ctx(all_users=all_users, updates=updates, bot=bot, alerts=[_ALERT])

    changed = run_alerts_worker_iteration(ctx=ctx)

    assert changed is True
    assert updates == [
        (7, "loc-1", {"last_check_ts": _NOW, "expected_last_check_ts": 0, "expected_interval_h": 2, "last_alert_signature": _SIGNATURE})
    ]
    assert all_users["8"] == snapshot_of_user_8
    assert [m["chat_id"] for m in bot.messages] == [7]


def test_run_alerts_worker_iteration_passes_snapshot_check_timestamp_as_expected_value(monkeypatch):
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: _NOW)
    stale_check = _NOW - 5 * 3600
    all_users = {"7": {"alert_subscriptions": [_sub("loc-1", last_check_ts=stale_check)]}}
    updates = []
    ctx = _worker_ctx(all_users=all_users, updates=updates, alerts=[])

    run_alerts_worker_iteration(ctx=ctx)

    assert updates == [
        (7, "loc-1", {"last_check_ts": _NOW, "expected_last_check_ts": stale_check, "expected_interval_h": 2, "last_alert_signature": None})
    ]


def test_run_alerts_worker_iteration_passes_snapshot_interval_as_expected_value(monkeypatch):
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: _NOW)
    every_six_hours = {**_sub("loc-1", last_check_ts=0), "interval_h": 6}
    all_users = {"7": {"alert_subscriptions": [every_six_hours]}}
    updates = []
    ctx = _worker_ctx(all_users=all_users, updates=updates, alerts=[_ALERT])

    run_alerts_worker_iteration(ctx=ctx)

    # Both snapshot values the worker acted on travel with the update, so the storage layer can tell whether
    # the user changed either of them (an interval change resets last_check_ts to the very same 0) meanwhile.
    assert updates == [
        (
            7,
            "loc-1",
            {
                "last_check_ts": _NOW,
                "expected_last_check_ts": 0,
                "expected_interval_h": 6,
                "last_alert_signature": _SIGNATURE,
            },
        )
    ]


def test_run_alerts_worker_iteration_updates_each_due_subscription_of_each_user_separately(monkeypatch):
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: _NOW)
    all_users = {
        "7": {"alert_subscriptions": [_sub("loc-1", last_check_ts=0), _sub("loc-2", last_check_ts=0)]},
        "8": {"alert_subscriptions": [_sub("loc-1", last_check_ts=0)]},  # same location_id, different user
        "9": {"alert_subscriptions": [_sub("loc-3", last_check_ts=_NOW - 10)]},
    }
    updates = []
    ctx = _worker_ctx(all_users=all_users, updates=updates, alerts=[])

    changed = run_alerts_worker_iteration(ctx=ctx)

    assert changed is True
    assert [(user_id, location_id) for user_id, location_id, _ in updates] == [(7, "loc-1"), (7, "loc-2"), (8, "loc-1")]
    assert all(kwargs["last_check_ts"] == _NOW and kwargs["last_alert_signature"] is None for _, _, kwargs in updates)
    assert all_users["9"]["alert_subscriptions"][0]["last_check_ts"] == _NOW - 10


def test_run_alerts_worker_iteration_writes_nothing_when_no_subscription_is_due(monkeypatch):
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: _NOW)
    all_users = {
        "7": {"alert_subscriptions": [_sub("loc-1", last_check_ts=_NOW - 30)]},  # not due yet
        "8": {"alert_subscriptions": [_sub("loc-2", last_check_ts=0, enabled=False)]},  # disabled
        "9": {"alert_subscriptions": []},  # nothing subscribed
    }
    updates = []
    ctx = _worker_ctx(all_users=all_users, updates=updates, alerts=[_ALERT])

    changed = run_alerts_worker_iteration(ctx=ctx)

    assert changed is False
    assert updates == []
    assert ctx.bot.messages == []


def test_run_alerts_worker_iteration_persists_check_timestamp_when_forecast_unavailable(monkeypatch):
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: _NOW)
    all_users = {
        "7": {"alert_subscriptions": [_sub("loc-1", last_check_ts=0)]},
        "8": {"alert_subscriptions": [_sub("loc-2", last_check_ts=_NOW - 5)]},
    }
    updates = []
    ctx = _worker_ctx(all_users=all_users, updates=updates)
    ctx.get_forecast_5d3h = lambda lat, lon: None

    changed = run_alerts_worker_iteration(ctx=ctx)

    assert changed is True
    assert updates == [
        (7, "loc-1", {"last_check_ts": _NOW, "expected_last_check_ts": 0, "expected_interval_h": 2, "last_alert_signature": None})
    ]


def test_run_alerts_worker_iteration_failed_send_updates_timestamp_but_not_signature(monkeypatch):
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: _NOW)
    all_users = {"7": {"alert_subscriptions": [_sub("loc-1", last_check_ts=0)]}}
    updates = []
    ctx = _worker_ctx(all_users=all_users, updates=updates, alerts=[_ALERT])

    def _failing_send(chat_id, text):
        raise RuntimeError("telegram is down")

    ctx.bot.send_message = _failing_send

    run_alerts_worker_iteration(ctx=ctx)

    sub = all_users["7"]["alert_subscriptions"][0]
    assert sub["last_alert_signature"] == ""  # so the alert is retried next time
    assert sub["last_check_ts"] == _NOW
    # signature=None means "leave the stored signature alone": the retry behaviour is unchanged.
    assert updates == [
        (7, "loc-1", {"last_check_ts": _NOW, "expected_last_check_ts": 0, "expected_interval_h": 2, "last_alert_signature": None})
    ]


def test_run_alerts_worker_iteration_state_update_failure_does_not_block_other_subscriptions(monkeypatch):
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: _NOW)
    all_users = {
        "7": {"alert_subscriptions": [_sub("loc-1", last_check_ts=0)]},
        "8": {"alert_subscriptions": [_sub("loc-2", last_check_ts=0)]},
    }
    updates = []
    logged = []

    def _update_state(user_id, location_id, **kwargs):
        if user_id == 7:
            raise RuntimeError("db unavailable")
        updates.append((user_id, location_id, kwargs))
        return True

    logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        exception=lambda *args, **kwargs: logged.append(args),
    )
    ctx = _worker_ctx(all_users=all_users, updates=updates, update_state=_update_state, logger=logger)

    changed = run_alerts_worker_iteration(ctx=ctx)

    assert changed is True
    assert [(user_id, location_id) for user_id, location_id, _ in updates] == [(8, "loc-2")]
    assert len(logged) == 1


def test_run_alerts_worker_iteration_tolerates_subscription_deleted_meanwhile(monkeypatch):
    monkeypatch.setattr("workers.alerts_worker.time.time", lambda: _NOW)
    all_users = {"7": {"alert_subscriptions": [_sub("loc-1", last_check_ts=0)]}}
    ctx = _worker_ctx(all_users=all_users, updates=[], alerts=[], update_state=lambda *args, **kwargs: False)

    changed = run_alerts_worker_iteration(ctx=ctx)

    assert changed is True  # the check itself happened; a missing row is not an error
