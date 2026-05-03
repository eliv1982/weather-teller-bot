from datetime import date
from types import SimpleNamespace
import sys
import types

telebot_module = types.ModuleType("telebot")
telebot_module.types = SimpleNamespace(
    Message=object,
    ReplyKeyboardMarkup=object,
    KeyboardButton=object,
    InlineKeyboardMarkup=object,
    InlineKeyboardButton=object,
    ReplyKeyboardRemove=lambda: "reply-keyboard-remove",
)
sys.modules.setdefault("telebot", telebot_module)
from flows import send_tomorrow_forecast_by_coordinates
from forecast_service import get_tomorrow_forecast_day, group_forecast_by_day
from session_store import SessionStore


class _FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


def _message(chat_id=123):
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id))


def test_send_tomorrow_forecast_stores_cache_and_renders_selected_day_directly():
    forecast_items = [
        {"dt_txt": "2026-05-02 12:00:00", "main": {"temp": 10}, "weather": [{"description": "ясно"}]},
        {"dt_txt": "2026-05-03 12:00:00", "main": {"temp": 15}, "weather": [{"description": "облачно"}]},
        {"dt_txt": "2026-05-03 15:00:00", "main": {"temp": 16}, "weather": [{"description": "облачно"}]},
    ]
    bot = _FakeBot()
    saved_users = {}
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
        get_forecast_5d3h=lambda lat, lon: forecast_items,
        group_forecast_by_day=group_forecast_by_day,
        get_tomorrow_forecast_day=lambda grouped: get_tomorrow_forecast_day(grouped, today=date(2026, 5, 2)),
        get_location_by_coordinates=lambda lat, lon: None,
        build_location_label=lambda location, show_coords=False: "Москва",
        load_user=lambda user_id: {},
        save_user=lambda user_id, data: saved_users.__setitem__(user_id, data),
        main_menu=lambda: "main-menu",
        format_tomorrow_forecast_response=lambda city, day, items: f"tomorrow {day} {city} {len(items)}",
        build_ai_action_keyboard=lambda text, callback_data: {"text": text, "callback_data": callback_data},
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_tomorrow_forecast_city"

    result = send_tomorrow_forecast_by_coordinates(
        _message(),
        7,
        55.75,
        37.61,
        "Москва",
        save_location=True,
        preferred_city_label="Москва",
        ctx=ctx,
        session_store=session_store,
    )

    assert result is True
    assert session_store.forecast_cache[7]["city"] == "Москва"
    assert list(session_store.forecast_cache[7]["grouped"].keys()) == ["02.05", "03.05"]
    assert 7 not in session_store.user_states
    assert saved_users[7]["city"] == "Москва"
    assert [message["text"] for message in bot.messages] == [
        "Прогноз на завтра готов.",
        "tomorrow 03.05 Москва 2",
        "✨ Хочешь короткое пояснение прогноза?",
    ]
    assert bot.messages[1]["reply_markup"] == "main-menu"
    assert bot.messages[-1]["reply_markup"] == {
        "text": "✨ Короткое пояснение прогноза",
        "callback_data": "ai_tomorrow_forecast_day:03.05",
    }


def test_send_tomorrow_forecast_handles_missing_tomorrow_without_crashing():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
        get_forecast_5d3h=lambda lat, lon: [
            {"dt_txt": "2026-05-04 12:00:00", "main": {"temp": 10}, "weather": [{"description": "ясно"}]},
        ],
        group_forecast_by_day=group_forecast_by_day,
        get_tomorrow_forecast_day=lambda grouped: get_tomorrow_forecast_day(grouped, today=date(2026, 5, 2)),
        get_location_by_coordinates=lambda lat, lon: None,
        build_location_label=lambda location, show_coords=False: "Москва",
        load_user=lambda user_id: {},
        save_user=lambda user_id, data: None,
        main_menu=lambda: "main-menu",
        format_tomorrow_forecast_response=lambda city, day, items: "unused",
        build_ai_action_keyboard=lambda text, callback_data: "unused",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_tomorrow_forecast_city"

    result = send_tomorrow_forecast_by_coordinates(
        _message(),
        7,
        55.75,
        37.61,
        "Москва",
        save_location=False,
        preferred_city_label="Москва",
        ctx=ctx,
        session_store=session_store,
    )

    assert result is False
    assert session_store.forecast_cache.get(7) is None
    assert 7 not in session_store.user_states
    assert bot.messages[-1]["text"] == (
        "Не нашла прогноз на завтра в ответе погодного сервиса. Попробуй открыть прогноз на 5 дней."
    )
