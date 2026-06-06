from types import SimpleNamespace

from handlers.callbacks_ai import handle_ai_callback


class _FakeBot:
    def __init__(self):
        self.messages = []
        self.answers = []

    def answer_callback_query(self, callback_id, text=None):
        self.answers.append((callback_id, text))

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


class _FakeAiService:
    def summarize_day_forecast(self, city_label, day_items):
        return f"old forecast for {city_label}: {len(day_items)}"

    def explain_tomorrow_forecast(self, city_label, day_items):
        return f"tomorrow explanation for {city_label}: {len(day_items)}"

    def explain_today_forecast(self, city_label, day_items, *, is_remaining_day=False):
        suffix = "remaining" if is_remaining_day else "today"
        return f"{suffix} explanation for {city_label}: {len(day_items)}"


def _call(data):
    return SimpleNamespace(
        id="cb1",
        data=data,
        from_user=SimpleNamespace(id=7),
        message=SimpleNamespace(chat=SimpleNamespace(id=123)),
    )


def _ctx(bot):
    return SimpleNamespace(
        bot=bot,
        ai_weather_service=_FakeAiService(),
        main_menu=lambda: "main-menu",
    )


def _session_store():
    return SimpleNamespace(
        forecast_cache={
            7: {
                "city": "Москва",
                "grouped": {
                    "03.05": [
                        {"dt_txt": "2026-05-03 09:00:00", "main": {"temp": 10}, "weather": [{"description": "ясно"}]}
                    ]
                },
            }
        },
        ai_current_snapshots={},
        ai_details_snapshots={},
    )


def test_tomorrow_ai_callback_uses_explanation_label_not_recommendation():
    bot = _FakeBot()

    handle_ai_callback(_call("ai_tomorrow_forecast_day:03.05"), ctx=_ctx(bot), session_store=_session_store())

    assert bot.messages[-1]["text"] == "✨ tomorrow explanation for Москва: 1"
    assert "Пояснение:" not in bot.messages[-1]["text"]
    assert "Рекомендация на день" not in bot.messages[-1]["text"]


def test_existing_forecast_day_ai_callback_keeps_recommendation_behavior():
    bot = _FakeBot()

    handle_ai_callback(_call("ai_forecast_day:03.05"), ctx=_ctx(bot), session_store=_session_store())

    assert bot.messages[-1]["text"] == "🪄 Рекомендация на день:\nold forecast for Москва: 1"


def test_today_ai_callback_uses_today_explanation_flow():
    bot = _FakeBot()

    handle_ai_callback(_call("ai_today_forecast_day:03.05"), ctx=_ctx(bot), session_store=_session_store())

    assert bot.messages[-1]["text"] == "✨ remaining explanation for Москва: 1"
    assert "Пояснение:" not in bot.messages[-1]["text"]
