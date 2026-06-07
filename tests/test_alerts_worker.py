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


def test_run_alerts_worker_iteration_sends_alert_and_persists_signature(monkeypatch):
    bot = _Bot()
    saved_payloads = []
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
        save_all_users=lambda payload: saved_payloads.append(payload),
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
    assert len(saved_payloads) == 1
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
    saved_payloads = []
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
        save_all_users=lambda payload: saved_payloads.append(payload),
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
    assert len(saved_payloads) == 1
    assert all_users["7"]["alert_subscriptions"][0]["last_check_ts"] == 1700000000
    assert bot.messages == []
