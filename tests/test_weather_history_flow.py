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

from flows import prepare_weather_history_by_coordinates, send_weather_history_by_date
from session_store import SessionStore


class _FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


def _message(chat_id=123):
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id))


def test_prepare_weather_history_by_coordinates_shows_date_picker():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        build_history_date_keyboard=lambda: "history-date-keyboard",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_city"

    result = prepare_weather_history_by_coordinates(
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
        "✅ Локация выбрана: Москва",
        "Выбери дату для архивной справки по Москва:",
    ]
    assert bot.messages[1]["reply_markup"] == "history-date-keyboard"
    assert session_store.user_states[7] == "waiting_history_date_pick"
    assert session_store.history_drafts[7] == {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
    }


def test_send_weather_history_by_date_renders_result(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        ai_weather_service=SimpleNamespace(
            explain_history_weather=lambda city, history: "По архивным данным день был спокойным."
        ),
        format_history_weather_response=lambda city, history, *, short_summary=None: (
            f"history {city} {history['weather_description']} {short_summary}"
        ),
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_custom_date"
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}
    monkeypatch.setattr(
        "flows.get_weather_history_by_date",
        lambda lat, lon, city, target_date: {
            "ok": True,
            "history": {"weather_description": "дождь"},
        },
    )

    result = send_weather_history_by_date(
        _message(),
        7,
        date(2026, 5, 1),
        ctx=ctx,
        session_store=session_store,
    )

    assert result is True
    assert [message["text"] for message in bot.messages] == [
        "✅ Выбрано: 01.05.2026",
        "history Москва дождь По архивным данным день был спокойным.",
    ]
    assert 7 not in session_store.user_states
    assert 7 not in session_store.history_drafts


def test_send_weather_history_by_date_can_skip_confirmation_when_it_was_already_shown(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        ai_weather_service=SimpleNamespace(
            explain_history_weather=lambda city, history: "По архивным данным день был спокойным."
        ),
        format_history_weather_response=lambda city, history, *, short_summary=None: (
            f"history {city} {history['weather_description']} {short_summary}"
        ),
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_date_pick"
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}
    monkeypatch.setattr(
        "flows.get_weather_history_by_date",
        lambda lat, lon, city, target_date: {
            "ok": True,
            "history": {"weather_description": "пасмурно"},
        },
    )

    result = send_weather_history_by_date(
        _message(),
        7,
        date(2026, 5, 2),
        send_confirmation=False,
        ctx=ctx,
        session_store=session_store,
    )

    assert result is True
    assert [message["text"] for message in bot.messages] == [
        "history Москва пасмурно По архивным данным день был спокойным.",
    ]


def test_send_weather_history_by_date_handles_error_and_cleans_runtime(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        format_history_weather_response=lambda city, history: "unused",
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_custom_date"
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}
    monkeypatch.setattr(
        "flows.get_weather_history_by_date",
        lambda lat, lon, city, target_date: {
            "ok": False,
            "error_message": "Не удалось разобрать архивные данные за эту дату. Попробуй выбрать другой день.",
        },
    )

    result = send_weather_history_by_date(
        _message(),
        7,
        date(2026, 5, 2),
        ctx=ctx,
        session_store=session_store,
    )

    assert result is False
    assert bot.messages == [
        {
            "chat_id": 123,
            "text": "Не удалось разобрать архивные данные за эту дату. Попробуй выбрать другой день.",
            "reply_markup": "main-menu",
        }
    ]
    assert 7 not in session_store.user_states
    assert 7 not in session_store.history_drafts
