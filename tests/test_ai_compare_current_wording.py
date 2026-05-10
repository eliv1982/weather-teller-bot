from types import SimpleNamespace

from handlers.locations import _ai_compare_after_two_locations, handle_locations_text
from handlers.states import WAITING_AI_COMPARE_MODE


class _Bot:
    def __init__(self):
        self.calls = []

    def send_message(self, *args, **kwargs):
        self.calls.append(("send_message", args, kwargs))


def test_current_compare_result_uses_comparison_title_without_verdict_heading():
    bot = _Bot()
    user_id = 5
    ctx = SimpleNamespace(
        bot=bot,
        get_current_weather=lambda lat, lon: {
            "main": {"temp": 12, "feels_like": 10, "humidity": 55},
            "wind": {"speed": 4},
            "weather": [{"description": "облачно"}],
        },
        ai_weather_service=SimpleNamespace(
            compare_two_locations_current_with_ai=lambda *args, **kwargs: "📍 Тольятти\n🌡 Температура: 12.0°C\n\n✨ Тольятти: прохладно и облачно. Влажность умеренная, ветер умеренный, осадков по текущим данным нет."
        ),
        main_menu=lambda: "main-menu",
    )
    session_store = SimpleNamespace(
        ai_compare_drafts={
            user_id: {
                "mode": "current",
                "loc_1": {"city_label": "Тольятти", "lat": 55.0, "lon": 37.0},
                "loc_2": {"city_label": "Москва", "lat": 55.7, "lon": 37.6},
            }
        },
        ai_compare_location_choices={user_id: ["stub"]},
        user_states={user_id: WAITING_AI_COMPARE_MODE},
    )
    message = SimpleNamespace(chat=SimpleNamespace(id=100))

    result = _ai_compare_after_two_locations(message, user_id, ctx=ctx, session_store=session_store)

    assert result is True
    body = bot.calls[-1][1][1]
    assert body == "✨ Сравнение локаций (сейчас)\n\n📍 Тольятти\n🌡 Температура: 12.0°C\n\n✨ Тольятти: прохладно и облачно. Влажность умеренная, ветер умеренный, осадков по текущим данным нет."
    assert "Сравнить локации" not in body
    assert "Вывод:" not in body


def test_compare_mode_accepts_new_emoji_button_labels():
    bot = _Bot()
    user_id = 9
    ctx = SimpleNamespace(
        bot=bot,
        ai_compare_location_method_menu=lambda: "location-method-menu",
    )
    session_store = SimpleNamespace(
        ai_compare_drafts={},
        user_states={user_id: WAITING_AI_COMPARE_MODE},
    )
    message = SimpleNamespace(text="⚖️ Сравнить сейчас", chat=SimpleNamespace(id=100))

    handled = handle_locations_text(
        message,
        user_id,
        WAITING_AI_COMPARE_MODE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.ai_compare_drafts[user_id]["mode"] == "current"
    assert bot.calls[-1][1][1] == "Введи название первой локации или выбери другой способ ниже:"

    bot.calls.clear()
    session_store.ai_compare_drafts.clear()
    message = SimpleNamespace(text="📅 Сравнить на дату", chat=SimpleNamespace(id=100))

    handled = handle_locations_text(
        message,
        user_id,
        WAITING_AI_COMPARE_MODE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.ai_compare_drafts[user_id]["mode"] == "date"
    assert bot.calls[-1][1][1] == "Введи название первой локации или выбери другой способ ниже:"
