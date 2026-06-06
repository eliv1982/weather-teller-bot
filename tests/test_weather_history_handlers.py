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

from handlers.callbacks_history import handle_history_callback
from handlers.history import handle_history_text
from session_store import SessionStore


class _FakeBot:
    def __init__(self):
        self.messages = []
        self.callback_answers = []
        self.edited_messages = []
        self.reply_markup_edits = []
        self.deleted_messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    def answer_callback_query(self, callback_id, text=None):
        self.callback_answers.append({"callback_id": callback_id, "text": text})

    def edit_message_text(self, text, chat_id=None, message_id=None, reply_markup=None):
        self.edited_messages.append(
            {"text": text, "chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup}
        )

    def edit_message_reply_markup(self, chat_id=None, message_id=None, reply_markup=None):
        self.reply_markup_edits.append(
            {"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup}
        )

    def delete_message(self, chat_id, message_id):
        self.deleted_messages.append({"chat_id": chat_id, "message_id": message_id})


def _message(text, chat_id=123, user_id=7):
    return SimpleNamespace(
        text=text,
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
    )


def _callback(data, chat_id=123, user_id=7):
    return SimpleNamespace(
        data=data,
        id="cb-1",
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=99),
    )


def test_handle_history_text_invalid_custom_date_keeps_state_and_reprompts():
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_custom_date"

    result = handle_history_text(
        _message("2026-02-31"),
        7,
        "waiting_history_custom_date",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
    )

    assert result is True
    assert session_store.user_states[7] == "waiting_history_custom_date"
    assert "Не получилось распознать дату" in bot.messages[-1]["text"]


def test_handle_history_text_future_custom_date_keeps_state_and_reprompts():
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_custom_date"

    result = handle_history_text(
        _message("2999-01-01"),
        7,
        "waiting_history_custom_date",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
    )

    assert result is True
    assert session_store.user_states[7] == "waiting_history_custom_date"
    assert "Нужна дата из прошлого" in bot.messages[-1]["text"]


def test_handle_history_cancel_callback_returns_to_location_input():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {"saved_locations": []},
        location_input_menu=lambda has_saved_locations=False: ("location-menu", has_saved_locations),
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_pick"
    session_store.history_location_choices[7] = [{"name": "Москва"}]

    handle_history_callback(
        _callback("history_cancel"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert session_store.user_states[7] == "waiting_history_city"
    assert 7 not in session_store.history_location_choices
    assert bot.deleted_messages == [{"chat_id": 123, "message_id": 99}]
    assert bot.messages[-1] == {
        "chat_id": 123,
        "text": "Введи название населенного пункта или выбери другой способ ниже:",
        "reply_markup": ("location-menu", False),
    }


def test_handle_history_menu_callback_clears_runtime_and_returns_main_menu():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        main_menu=lambda: "main-menu",
        load_user=lambda user_id: {"saved_locations": []},
        location_input_menu=lambda has_saved_locations=False: "location-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_date_pick"
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 1.0, "lon": 2.0}
    session_store.history_location_choices[7] = [{"name": "Москва"}]

    handle_history_callback(
        _callback("history_menu"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert 7 not in session_store.user_states
    assert 7 not in session_store.history_drafts
    assert 7 not in session_store.history_location_choices
    assert bot.deleted_messages == [{"chat_id": 123, "message_id": 99}]
    assert bot.messages[-1] == {
        "chat_id": 123,
        "text": "Главное меню.",
        "reply_markup": "main-menu",
    }


def test_handle_history_custom_date_callback_clears_inline_menu_and_prompts_for_input():
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}

    handle_history_callback(
        _callback("history_date_custom"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert session_store.user_states[7] == "waiting_history_custom_date"
    assert bot.deleted_messages == [{"chat_id": 123, "message_id": 99}]
    assert [message["text"] for message in bot.messages] == [
        "✅ Выбрано: ввести дату вручную",
        "Введи дату в формате YYYY-MM-DD или DD.MM.YYYY.\nНужна дата из прошлого.",
    ]


def test_handle_history_preset_callback_clears_inline_menu_and_sends_date_without_duplicate_confirmation():
    bot = _FakeBot()
    sent_dates = []
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()

    handle_history_callback(
        _callback("history_date_preset:yesterday"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda message, user_id, target_date, **kwargs: sent_dates.append(
            {"user_id": user_id, "target_date": target_date, "kwargs": kwargs}
        ),
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert bot.deleted_messages == [{"chat_id": 123, "message_id": 99}]
    assert bot.messages[0]["text"].startswith("✅ Выбрано: ")
    assert sent_dates and sent_dates[0]["kwargs"]["send_confirmation"] is False
