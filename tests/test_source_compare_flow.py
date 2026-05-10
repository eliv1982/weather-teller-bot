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

from flows import send_source_compare_by_coordinates
from session_store import SessionStore


class _FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


def _message(chat_id=123):
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id))


def test_send_source_compare_by_coordinates_renders_result(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        format_source_compare_response=lambda city, ow, om: f"compare {city} {ow['dominant_description']} {om['dominant_description']}",
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_source_compare_city"
    session_store.source_compare_location_choices[7] = [{"name": "Москва"}]
    monkeypatch.setattr(
        "flows.compare_tomorrow_sources",
        lambda lat, lon, city: {
            "ok": True,
            "openweather": {"dominant_description": "ясно"},
            "open_meteo": {"dominant_description": "облачно"},
        },
    )

    result = send_source_compare_by_coordinates(
        _message(),
        7,
        55.75,
        37.61,
        "Москва",
        preferred_city_label="Москва",
        ctx=ctx,
        session_store=session_store,
    )

    assert result is True
    assert [message["text"] for message in bot.messages] == [
        "Сравнение прогнозов готово.",
        "compare Москва ясно облачно",
    ]
    assert 7 not in session_store.user_states
    assert 7 not in session_store.source_compare_location_choices


def test_send_source_compare_by_coordinates_handles_error(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        format_source_compare_response=lambda city, ow, om: "unused",
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_source_compare_city"
    monkeypatch.setattr(
        "flows.compare_tomorrow_sources",
        lambda lat, lon, city: {
            "ok": False,
            "error_message": "Не удалось сверить источники: один из прогнозов сейчас недоступен.",
        },
    )

    result = send_source_compare_by_coordinates(
        _message(),
        7,
        55.75,
        37.61,
        "Москва",
        preferred_city_label="Москва",
        ctx=ctx,
        session_store=session_store,
    )

    assert result is False
    assert bot.messages[-1]["text"] == "Не удалось сверить источники: один из прогнозов сейчас недоступен."
