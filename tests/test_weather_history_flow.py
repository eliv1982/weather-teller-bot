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

from flows import (
    prepare_weather_history_by_coordinates,
    send_history_monthly_report,
    send_weather_history_by_date,
    start_weather_history_flow,
)
from flows_history import (
    prepare_weather_history_by_coordinates as direct_prepare_weather_history_by_coordinates,
    send_history_monthly_report as direct_send_history_monthly_report,
    send_weather_history_by_date as direct_send_weather_history_by_date,
    start_weather_history_flow as direct_start_weather_history_flow,
)
from session_store import SessionStore


class _FakeBot:
    def __init__(self):
        self.messages = []
        self.deleted_messages = []
        self._next_msg_id = 100

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        msg_id = self._next_msg_id
        self._next_msg_id += 1
        return SimpleNamespace(message_id=msg_id)

    def delete_message(self, chat_id, message_id):
        self.deleted_messages.append({"chat_id": chat_id, "message_id": message_id})


def _message(chat_id=123, user_id=7):
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id), from_user=SimpleNamespace(id=user_id))


def test_start_weather_history_flow_shows_section_menu():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        build_history_section_keyboard=lambda: "history-section-keyboard",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_city"
    session_store.history_drafts[7] = {"city_label": "Старое"}

    start_weather_history_flow(_message(), ctx=ctx, session_store=session_store)

    assert session_store.user_states[7] == "waiting_history_section"
    assert 7 not in session_store.history_drafts
    assert bot.messages == [
        {"chat_id": 123, "text": "Что посмотрим?", "reply_markup": "history-section-keyboard"}
    ]


def test_prepare_weather_history_by_coordinates_shows_date_picker_for_daily_section():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        build_history_date_keyboard=lambda: "history-date-keyboard",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_city"
    session_store.history_drafts[7] = {"history_section": "daily"}

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
        "history_section": "daily",
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
    }


def test_prepare_weather_history_by_coordinates_shows_climate_mode_for_climate_section():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        build_history_climate_mode_keyboard=lambda: "history-climate-mode-keyboard",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_city"
    session_store.history_drafts[7] = {"history_section": "climate"}

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
        "Выбери режим климатической справки по Москва:",
    ]
    assert bot.messages[1]["reply_markup"] == "history-climate-mode-keyboard"
    assert session_store.user_states[7] == "waiting_history_climate_mode"
    assert session_store.history_drafts[7] == {
        "history_section": "climate",
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
        "✅ Дата введена: 01.05.2026",
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


def test_send_history_monthly_report_renders_concrete_month_and_confirms_year(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        ai_weather_service=SimpleNamespace(
            explain_monthly_climate=lambda city, report: "По архивным данным месяц был умеренно прохладным."
        ),
        format_history_monthly_climate_response=lambda city, report, *, short_summary=None: (
            f"monthly {city} {report['mode']} {short_summary}"
        ),
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_climate_year"
    session_store.history_drafts[7] = {
        "history_section": "climate",
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_year",
        "monthly_month": 1,
        "monthly_year": 2020,
    }
    monkeypatch.setattr(
        "flows.get_monthly_history_for_month",
        lambda lat, lon, city, year, month: {
            "ok": True,
            "report": {"mode": "monthly_year", "year": year, "month": month},
        },
    )

    result = send_history_monthly_report(
        _message(),
        7,
        ctx=ctx,
        session_store=session_store,
    )

    assert result is True
    assert [message["text"] for message in bot.messages] == [
        "✅ Год выбран: 2020",
        "monthly Москва monthly_year По архивным данным месяц был умеренно прохладным.",
    ]
    assert 7 not in session_store.user_states
    assert 7 not in session_store.history_drafts


def test_send_history_monthly_report_renders_normals_without_year_confirmation(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        ai_weather_service=SimpleNamespace(
            explain_monthly_climate=lambda city, report: "Это архивная справка по данным за 1991-2020."
        ),
        format_history_monthly_climate_response=lambda city, report, *, short_summary=None: (
            f"monthly {city} {report['mode']} {short_summary}"
        ),
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_climate_month"
    session_store.history_drafts[7] = {
        "history_section": "climate",
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_normals",
        "monthly_month": 1,
    }
    monkeypatch.setattr(
        "flows.get_monthly_climate_normals",
        lambda lat, lon, city, month: {
            "ok": True,
            "report": {"mode": "monthly_normals", "month": month},
        },
    )

    result = send_history_monthly_report(
        _message(),
        7,
        send_year_confirmation=False,
        ctx=ctx,
        session_store=session_store,
    )

    assert result is True
    assert [message["text"] for message in bot.messages] == [
        "Считаю среднемесячные показатели по архивным данным, это может занять несколько секунд.",
        "monthly Москва monthly_normals Это архивная справка по данным за 1991-2020.",
    ]
    # Wait message was sent first (message_id=100) and then deleted best-effort.
    assert bot.deleted_messages == [{"chat_id": 123, "message_id": 100}]


def test_send_history_monthly_report_deletes_wait_message_on_normals_error(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.history_drafts[7] = {
        "history_section": "climate",
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_normals",
        "monthly_month": 1,
    }
    monkeypatch.setattr(
        "flows.get_monthly_climate_normals",
        lambda lat, lon, city, month: {
            "ok": False,
            "error_message": "Не удалось получить климатические данные.",
        },
    )

    result = send_history_monthly_report(
        _message(),
        7,
        send_year_confirmation=False,
        ctx=ctx,
        session_store=session_store,
    )

    assert result is False
    assert any("Считаю среднемесячные показатели" in msg["text"] for msg in bot.messages)
    # Wait message deleted even on error.
    assert bot.deleted_messages == [{"chat_id": 123, "message_id": 100}]


def test_send_history_monthly_report_deletes_year_prompt_for_monthly_year(monkeypatch):
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        ai_weather_service=SimpleNamespace(
            explain_monthly_climate=lambda city, report: "AI summary."
        ),
        format_history_monthly_climate_response=lambda city, report, *, short_summary=None: (
            f"monthly {city} {report['mode']}"
        ),
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.history_drafts[7] = {
        "history_section": "climate",
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "monthly_mode": "monthly_year",
        "monthly_month": 1,
        "monthly_year": 2020,
        "prompt_message_id": 77,
    }
    monkeypatch.setattr(
        "flows.get_monthly_history_for_month",
        lambda lat, lon, city, year, month: {
            "ok": True,
            "report": {"mode": "monthly_year", "year": year, "month": month},
        },
    )

    result = send_history_monthly_report(
        _message(),
        7,
        ctx=ctx,
        session_store=session_store,
    )

    assert result is True
    # "Введи год" prompt (message_id=77) deleted before the result is shown.
    assert {"chat_id": 123, "message_id": 77} in bot.deleted_messages
    # Confirmations and result messages remain.
    texts = [msg["text"] for msg in bot.messages]
    assert "✅ Год выбран: 2020" in texts


def test_send_weather_history_by_date_deletes_date_prompt_on_success(monkeypatch):
    """date_prompt_message_id in draft is deleted best-effort when result is shown."""
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        ai_weather_service=None,
        format_history_weather_response=lambda city, history, *, short_summary=None: "report",
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.history_drafts[7] = {
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
        "date_prompt_message_id": 200,
    }
    monkeypatch.setattr(
        "flows.get_weather_history_by_date",
        lambda lat, lon, city, target_date: {"ok": True, "history": {"weather_description": "ясно"}},
    )

    result = send_weather_history_by_date(
        _message(),
        7,
        date(2024, 6, 1),
        ctx=ctx,
        session_store=session_store,
    )

    assert result is True
    assert {"chat_id": 123, "message_id": 200} in bot.deleted_messages


def test_history_flow_functions_are_importable_from_flows_history():
    assert callable(direct_prepare_weather_history_by_coordinates)
    assert callable(direct_send_history_monthly_report)
    assert callable(direct_send_weather_history_by_date)
    assert callable(direct_start_weather_history_flow)


def test_start_weather_history_flow_works_via_direct_flows_history_import():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        build_history_section_keyboard=lambda: "history-section-keyboard",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_history_city"
    session_store.history_drafts[7] = {"city_label": "Старое"}

    direct_start_weather_history_flow(_message(), ctx=ctx, session_store=session_store)

    assert session_store.user_states[7] == "waiting_history_section"
    assert 7 not in session_store.history_drafts
    assert bot.messages == [
        {"chat_id": 123, "text": "Что посмотрим?", "reply_markup": "history-section-keyboard"}
    ]
