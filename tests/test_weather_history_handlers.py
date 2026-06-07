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
        self._next_msg_id = 100

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        msg_id = self._next_msg_id
        self._next_msg_id += 1
        return SimpleNamespace(message_id=msg_id, chat=SimpleNamespace(id=chat_id))

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


def _message(text, chat_id=123, user_id=7, message_id=None):
    return SimpleNamespace(
        text=text,
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        message_id=message_id,
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
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}

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
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}

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


def test_handle_history_text_waiting_section_reprompts_with_section_keyboard():
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot, build_history_section_keyboard=lambda: "history-section-menu")
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_section"

    result = handle_history_text(
        _message("Москва"),
        7,
        "waiting_history_section",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
    )

    assert result is True
    assert bot.messages[-1] == {
        "chat_id": 123,
        "text": "Выбери раздел кнопкой ниже или нажми «⬅️ В меню».",
        "reply_markup": "history-section-menu",
    }


def test_handle_history_section_daily_callback_prompts_for_location():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {"saved_locations": []},
        location_input_menu=lambda has_saved_locations=False: ("location-menu", has_saved_locations),
    )
    session_store = SessionStore()

    handle_history_callback(
        _callback("history_section:daily"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert session_store.user_states[7] == "waiting_history_city"
    assert session_store.history_drafts[7]["history_section"] == "daily"
    assert bot.deleted_messages == [{"chat_id": 123, "message_id": 99}]
    assert [message["text"] for message in bot.messages] == [
        "✅ Раздел выбран: на дату",
        "Введи название населенного пункта или выбери другой способ ниже:",
    ]


def test_handle_history_section_climate_callback_prompts_for_location():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {"saved_locations": []},
        location_input_menu=lambda has_saved_locations=False: ("location-menu", has_saved_locations),
    )
    session_store = SessionStore()

    handle_history_callback(
        _callback("history_section:climate"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert session_store.user_states[7] == "waiting_history_city"
    assert session_store.history_drafts[7]["history_section"] == "climate"
    assert [message["text"] for message in bot.messages] == [
        "✅ Раздел выбран: средние климатические показатели",
        "Введи название населенного пункта или выбери другой способ ниже:",
    ]


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
        "✅ Ввод даты вручную",
        "Введи дату в формате YYYY-MM-DD, DD.MM.YYYY, 8/6/2025 или 5 июня 2026.\nНужна дата из прошлого.",
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


def test_handle_history_text_short_year_date_prompts_for_year_clarification(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        build_history_year_clarification_keyboard=lambda options: [item.isoformat() for item in options],
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_custom_date"
    session_store.history_drafts[7] = {"history_section": "daily", "city_label": "Москва", "lat": 55.75, "lon": 37.61}
    monkeypatch.setattr(
        "handlers.history.resolve_history_date_input",
        lambda raw_value: SimpleNamespace(
            parsed_date=None,
            error_message=None,
            clarification_dates=[date(2025, 6, 8), date(1925, 6, 8)],
        ),
    )

    result = handle_history_text(
        _message("8/06/25"),
        7,
        "waiting_history_custom_date",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
    )

    assert result is True
    assert session_store.user_states[7] == "waiting_history_custom_date"
    assert session_store.history_drafts[7]["pending_history_date_options"] == ["2025-06-08", "1925-06-08"]
    assert bot.messages[-1] == {
        "chat_id": 123,
        "text": "Уточни год:",
        "reply_markup": ["2025-06-08", "1925-06-08"],
    }


def test_handle_history_date_year_callback_sends_selected_date():
    bot = _FakeBot()
    sent_dates = []
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.history_drafts[7] = {
        "history_section": "daily",
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "pending_history_date_options": ["2025-06-08", "1925-06-08"],
    }

    handle_history_callback(
        _callback("history_date_year:2025-06-08"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda message, user_id, target_date, **kwargs: sent_dates.append(
            {"chat_id": message.chat.id, "user_id": user_id, "target_date": target_date, "kwargs": kwargs}
        ),
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert bot.deleted_messages == [{"chat_id": 123, "message_id": 99}]
    assert bot.messages == [{"chat_id": 123, "text": "✅ Выбрано: 08.06.2025", "reply_markup": None}]
    assert sent_dates == [
        {
            "chat_id": 123,
            "user_id": 7,
            "target_date": date(2025, 6, 8),
            "kwargs": {"send_confirmation": False},
        }
    ]


def test_handle_history_climate_open_callback_shows_mode_menu():
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot, build_history_climate_mode_keyboard=lambda: "climate-mode-menu")
    session_store = SessionStore()
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}

    handle_history_callback(
        _callback("history_climate_open"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert session_store.user_states[7] == "waiting_history_climate_mode"
    assert bot.deleted_messages == [{"chat_id": 123, "message_id": 99}]
    assert bot.messages[-1] == {
        "chat_id": 123,
        "text": "Выбери режим климатической справки по Москва:",
        "reply_markup": "climate-mode-menu",
    }


def test_handle_history_climate_mode_callback_shows_month_menu():
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot, build_history_month_keyboard=lambda: "month-menu")
    session_store = SessionStore()
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}

    handle_history_callback(
        _callback("history_climate_mode:monthly_normals"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert session_store.user_states[7] == "waiting_history_climate_month"
    assert session_store.history_drafts[7]["monthly_mode"] == "monthly_normals"
    assert [message["text"] for message in bot.messages] == [
        "✅ Режим выбран: среднемесячные показатели",
        "Выбери месяц:",
    ]
    assert bot.messages[-1]["reply_markup"] == "month-menu"


def test_handle_history_climate_month_callback_for_year_mode_prompts_for_year():
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.history_drafts[7] = {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_year",
    }

    handle_history_callback(
        _callback("history_climate_month:1"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert session_store.user_states[7] == "waiting_history_climate_year"
    assert session_store.history_drafts[7]["monthly_month"] == 1
    assert [message["text"] for message in bot.messages] == [
        "✅ Месяц выбран: январь",
        "Введи год, например 2020.",
    ]


def test_handle_history_climate_month_callback_for_normals_sends_report():
    bot = _FakeBot()
    sent = []
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.history_drafts[7] = {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_normals",
    }

    handle_history_callback(
        _callback("history_climate_month:1"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=lambda message, user_id, **kwargs: sent.append(
            {"chat_id": message.chat.id, "user_id": user_id, "kwargs": kwargs}
        ),
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert bot.messages == [{"chat_id": 123, "text": "✅ Месяц выбран: январь", "reply_markup": None}]
    assert sent == [{"chat_id": 123, "user_id": 7, "kwargs": {"send_year_confirmation": False}}]


def test_handle_history_text_valid_monthly_year_input_sends_report():
    bot = _FakeBot()
    sent = []
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_climate_year"
    session_store.history_drafts[7] = {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_year",
        "monthly_month": 1,
    }

    result = handle_history_text(
        _message("2020"),
        7,
        "waiting_history_climate_year",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=lambda message, user_id: sent.append((message.chat.id, user_id)) or True,
    )

    assert result is True
    assert session_store.history_drafts[7]["monthly_year"] == 2020
    assert sent == [(123, 7)]


def test_handle_history_text_future_monthly_year_input_keeps_state_and_reprompts():
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_climate_year"
    session_store.history_drafts[7] = {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_year",
        "monthly_month": 6,
    }

    result = handle_history_text(
        _message("2026-07"),
        7,
        "waiting_history_climate_year",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=lambda *args, **kwargs: True,
    )

    assert result is True
    assert session_store.user_states[7] == "waiting_history_climate_year"
    assert "Будущий месяц" in bot.messages[-1]["text"]


def test_handle_history_text_missing_monthly_draft_resets_state_and_prompts_restart():
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot, main_menu=lambda: "main-menu")
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_climate_year"

    result = handle_history_text(
        _message("2020"),
        7,
        "waiting_history_climate_year",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=lambda *args, **kwargs: True,
    )

    assert result is True
    assert 7 not in session_store.user_states
    assert 7 not in session_store.history_drafts
    assert bot.messages[-1] == {
        "chat_id": 123,
        "text": "Начни историю погоды заново.",
        "reply_markup": "main-menu",
    }


def test_handle_history_text_future_short_year_shows_warning_with_clarification(monkeypatch):
    """When 20YY is a future date, the clarification prompt explains it."""
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        build_history_year_clarification_keyboard=lambda options: [item.isoformat() for item in options],
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_custom_date"
    session_store.history_drafts[7] = {"history_section": "daily", "city_label": "Москва", "lat": 55.75, "lon": 37.61}

    monkeypatch.setattr(
        "handlers.history.resolve_history_date_input",
        lambda raw_value: SimpleNamespace(
            parsed_date=None,
            error_message=None,
            clarification_dates=[date(1926, 7, 15)],
        ),
    )
    monkeypatch.setattr(
        "handlers.history.build_two_digit_year_future_warning",
        lambda raw_value: (
            "15.07.2026 пока будущая дата, поэтому для архивной справки доступен только 15.07.1926."
        ),
    )

    result = handle_history_text(
        _message("15.07.26"),
        7,
        "waiting_history_custom_date",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
    )

    assert result is True
    clarification_msg = bot.messages[-1]
    assert "пока будущая дата" in clarification_msg["text"]
    assert "15.07.2026" in clarification_msg["text"]
    assert "15.07.1926" in clarification_msg["text"]
    assert "Уточни год:" in clarification_msg["text"]
    assert clarification_msg["reply_markup"] == ["1926-07-15"]


def test_handle_history_text_past_short_year_shows_plain_clarification(monkeypatch):
    """When both 20YY and 19YY are valid past dates, no warning is prepended."""
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        build_history_year_clarification_keyboard=lambda options: [item.isoformat() for item in options],
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_custom_date"
    session_store.history_drafts[7] = {"history_section": "daily", "city_label": "Москва", "lat": 55.75, "lon": 37.61}

    monkeypatch.setattr(
        "handlers.history.resolve_history_date_input",
        lambda raw_value: SimpleNamespace(
            parsed_date=None,
            error_message=None,
            clarification_dates=[date(2025, 6, 8), date(1925, 6, 8)],
        ),
    )
    monkeypatch.setattr(
        "handlers.history.build_two_digit_year_future_warning",
        lambda raw_value: None,
    )

    result = handle_history_text(
        _message("8/06/25"),
        7,
        "waiting_history_custom_date",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
    )

    assert result is True
    clarification_msg = bot.messages[-1]
    assert clarification_msg["text"] == "Уточни год:"
    assert clarification_msg["reply_markup"] == ["2025-06-08", "1925-06-08"]


def test_handle_history_climate_month_callback_saves_prompt_message_id_for_year_mode():
    """prompt_message_id is saved in draft so flows.py can delete it after result."""
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.history_drafts[7] = {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_year",
    }

    handle_history_callback(
        _callback("history_climate_month:3"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert session_store.user_states[7] == "waiting_history_climate_year"
    draft = session_store.history_drafts[7]
    assert draft["monthly_month"] == 3
    # message_id of "Введи год" prompt is saved so it can be cleaned up later.
    assert "prompt_message_id" in draft
    assert isinstance(draft["prompt_message_id"], int)


def test_handle_history_climate_back_to_modes_clears_prompt_message_id():
    """Navigating back to mode selection deletes the 'Введи год' prompt if present."""
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot, build_history_climate_mode_keyboard=lambda: "mode-menu")
    session_store = SessionStore()
    session_store.history_drafts[7] = {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_year",
        "monthly_month": 3,
        "prompt_message_id": 77,
    }

    handle_history_callback(
        _callback("history_climate_back_to_modes"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    # prompt_message_id is popped from draft
    assert "prompt_message_id" not in session_store.history_drafts.get(7, {})
    # best-effort delete was attempted
    assert {"chat_id": 123, "message_id": 77} in bot.deleted_messages


def test_handle_history_text_climate_year_tries_to_delete_user_message():
    """After a valid year is entered the user's typed message is scheduled for deletion."""
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_climate_year"
    session_store.history_drafts[7] = {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_year",
        "monthly_month": 3,
    }

    stub_monthly_report_called = []

    def _stub_send_monthly_report(msg, uid):
        stub_monthly_report_called.append((msg, uid))
        return True

    handle_history_text(
        _message("2020", message_id=555),
        7,
        "waiting_history_climate_year",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        send_history_monthly_report=_stub_send_monthly_report,
    )

    assert stub_monthly_report_called, "send_history_monthly_report should have been called"
    # Best-effort deletion of user typed year message was attempted.
    assert {"chat_id": 123, "message_id": 555} in bot.deleted_messages


def test_handle_history_text_custom_date_tries_to_delete_user_message():
    """After a valid date is entered the user's typed message is scheduled for deletion."""
    from datetime import date as _date

    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_custom_date"
    session_store.history_drafts[7] = {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
    }

    sent_to_date_sender: list = []

    def _stub_date_sender(msg, uid, parsed_date):
        sent_to_date_sender.append(parsed_date)
        return True

    handle_history_text(
        _message("01.01.2020", message_id=888),
        7,
        "waiting_history_custom_date",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=_stub_date_sender,
    )

    assert sent_to_date_sender, "send_weather_history_by_date should have been called"
    # Best-effort deletion of user typed date message was attempted.
    assert {"chat_id": 123, "message_id": 888} in bot.deleted_messages


# ---------------------------------------------------------------------------
# Wording: manual-date mode and typed-date confirmation
# ---------------------------------------------------------------------------

def test_manual_date_mode_button_shows_correct_confirmation():
    """Pressing the manual date entry button shows '✅ Ввод даты вручную', not '✅ Выбрано: ...'."""
    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}

    handle_history_callback(
        _callback("history_date_custom"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *a, **kw: None,
        send_weather_history_by_date=lambda *a, **kw: True,
        send_history_monthly_report=lambda *a, **kw: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    texts = [m["text"] for m in bot.messages]
    assert "✅ Ввод даты вручную" in texts
    assert not any(t.startswith("✅ Выбрано:") for t in texts)


def test_typed_date_confirmation_uses_data_vvedena_wording():
    """After typing a date, confirmation shows '✅ Дата введена: DD.MM.YYYY'."""
    from datetime import date as _date

    bot = _FakeBot()
    ctx = SimpleNamespace(bot=bot)
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_custom_date"
    session_store.history_drafts[7] = {"city_label": "Москва", "lat": 55.75, "lon": 37.61}

    confirmed_dates: list = []

    def _stub_date_sender(msg, uid, parsed_date):
        confirmed_dates.append(parsed_date)
        return True

    handle_history_text(
        _message("17.07.2025"),
        7,
        "waiting_history_custom_date",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *a, **kw: None,
        send_weather_history_by_date=_stub_date_sender,
    )

    assert confirmed_dates == [_date(2025, 7, 17)]
    # "✅ Дата введена:" is sent by send_weather_history_by_date which we stubbed,
    # so here we only verify the stub was called (wording tested in test_weather_history_flow.py).


# ---------------------------------------------------------------------------
# Location user-message cleanup
# ---------------------------------------------------------------------------

def test_handle_history_city_text_deletes_user_message_after_single_geocode_result(monkeypatch):
    """When exactly one geocode result is found, user's typed city message is deleted."""
    bot = _FakeBot()

    found_location = {
        "name": "Saint Petersburg",
        "local_names": {"ru": "Санкт-Петербург"},
        "lat": 59.95,
        "lon": 30.32,
        "country": "RU",
        "state": "Saint Petersburg",
    }

    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda uid: {},
        location_input_menu=lambda **kw: "loc-menu",
        get_location_by_coordinates=lambda lat, lon: None,
        build_location_label=lambda loc, **kw: "Санкт-Петербург",
        build_geocode_item_with_disambiguated_label=lambda locs, idx: dict(
            locs[idx], label="Санкт-Петербург"
        ),
        build_scenario_location_choice_keyboard=lambda locs, scenario: "choice-kb",
        main_menu=lambda: "main-menu",
    )

    monkeypatch.setattr(
        "handlers.history.find_locations_with_assist",
        lambda query, **kw: {"locations": [found_location]},
    )

    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_city"

    prepare_calls: list = []

    handle_history_text(
        _message("питер", message_id=444),
        7,
        "waiting_history_city",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *a, **kw: prepare_calls.append(a) or True,
        send_weather_history_by_date=lambda *a, **kw: True,
    )

    assert prepare_calls, "prepare_weather_history_by_coordinates was not called"
    assert {"chat_id": 123, "message_id": 444} in bot.deleted_messages


def test_handle_history_city_text_no_delete_on_geocode_error(monkeypatch):
    """When geocoding finds nothing, user's typed message is NOT deleted."""
    bot = _FakeBot()

    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda uid: {},
        location_input_menu=lambda **kw: "loc-menu",
        get_location_by_coordinates=lambda lat, lon: None,
        build_location_label=lambda loc, **kw: "",
        build_geocode_item_with_disambiguated_label=lambda locs, idx: {},
        build_scenario_location_choice_keyboard=lambda locs, scenario: "choice-kb",
        main_menu=lambda: "main-menu",
    )

    monkeypatch.setattr(
        "handlers.history.find_locations_with_assist",
        lambda query, **kw: {"locations": []},
    )

    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_city"
    session_store.history_drafts[7] = {
        "history_section": "daily",
        "location_prompt_message_id": 321,
    }

    handle_history_text(
        _message("несуществующийгород12345", message_id=555),
        7,
        "waiting_history_city",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *a, **kw: True,
        send_weather_history_by_date=lambda *a, **kw: True,
    )

    assert {"chat_id": 123, "message_id": 555} not in bot.deleted_messages
    assert {"chat_id": 123, "message_id": 321} not in bot.deleted_messages


# ---------------------------------------------------------------------------
# Prompt message_id tracking
# ---------------------------------------------------------------------------


def test_handle_history_section_daily_saves_location_prompt_message_id():
    """history_section:daily saves location_prompt_message_id in draft for later cleanup."""
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {"saved_locations": []},
        location_input_menu=lambda has_saved_locations=False: ("location-menu", has_saved_locations),
    )
    session_store = SessionStore()

    handle_history_callback(
        _callback("history_section:daily"),
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *args, **kwargs: None,
        send_weather_history_by_date=lambda *args, **kwargs: True,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    draft = session_store.history_drafts.get(7, {})
    assert "location_prompt_message_id" in draft
    assert isinstance(draft["location_prompt_message_id"], int)


def test_handle_history_custom_date_saves_date_prompt_message_id():
    """history_date_custom saves date_prompt_message_id in draft for later cleanup."""
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

    draft = session_store.history_drafts.get(7, {})
    assert "date_prompt_message_id" in draft
    assert isinstance(draft["date_prompt_message_id"], int)


def test_handle_history_city_text_deletes_location_prompt_after_single_geocode(monkeypatch):
    """Both user typed message AND location_prompt_message_id are deleted after single geocode match."""
    bot = _FakeBot()

    found_location = {
        "name": "Shanghai",
        "local_names": {"ru": "Шанхай"},
        "lat": 31.23,
        "lon": 121.47,
        "country": "CN",
        "state": "Shanghai",
    }

    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda uid: {},
        location_input_menu=lambda **kw: "loc-menu",
        get_location_by_coordinates=lambda lat, lon: None,
        build_location_label=lambda loc, **kw: "Шанхай (Китай)",
        build_geocode_item_with_disambiguated_label=lambda locs, idx: dict(locs[idx], label="Шанхай"),
        build_scenario_location_choice_keyboard=lambda locs, scenario: "choice-kb",
        main_menu=lambda: "main-menu",
    )

    monkeypatch.setattr(
        "handlers.history.find_locations_with_assist",
        lambda query, **kw: {"locations": [found_location]},
    )

    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_city"
    session_store.history_drafts[7] = {
        "history_section": "daily",
        "location_prompt_message_id": 321,
    }

    prepare_calls: list = []

    handle_history_text(
        _message("шанхай", message_id=444),
        7,
        "waiting_history_city",
        ctx=ctx,
        session_store=session_store,
        prepare_weather_history_by_coordinates=lambda *a, **kw: prepare_calls.append(a) or True,
        send_weather_history_by_date=lambda *a, **kw: True,
    )

    assert prepare_calls, "prepare_weather_history_by_coordinates was not called"
    assert {"chat_id": 123, "message_id": 444} in bot.deleted_messages
    assert {"chat_id": 123, "message_id": 321} in bot.deleted_messages
