"""Tests for AI compare-by-date callback UX (cleanup, post-result actions, another date)."""

from types import SimpleNamespace

from telebot import types

import keyboards
from handlers.callbacks_locations import handle_ai_compare_callback
from handlers.states import WAITING_AI_COMPARE_DATE_PICK


class _Bot:
    def __init__(self):
        self.calls = []

    def answer_callback_query(self, *args, **kwargs):
        self.calls.append(("answer_callback_query", args, kwargs))

    def send_message(self, *args, **kwargs):
        self.calls.append(("send_message", args, kwargs))

    def edit_message_text(self, *args, **kwargs):
        self.calls.append(("edit_message_text", args, kwargs))

    def edit_message_reply_markup(self, *args, **kwargs):
        self.calls.append(("edit_message_reply_markup", args, kwargs))

    def delete_message(self, *args, **kwargs):
        self.calls.append(("delete_message", args, kwargs))


def _call(*, data: str, user_id: int = 42, chat_id: int = 100, message_id: int = 500):
    return SimpleNamespace(
        id="cq",
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=message_id,
        ),
    )


def _flat_inline_buttons(markup: types.InlineKeyboardMarkup) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for row in markup.keyboard:
        for btn in row:
            out.append((btn.text, btn.callback_data))
    return out


def test_date_pick_marks_choice_message_with_day_label():
    bot = _Bot()
    user_id = 7
    selected_day = "04.05"
    draft = {
        "mode": "date",
        "available_days": [selected_day, "05.05"],
        "grouped_1": {selected_day: [{"dt": 1}]},
        "grouped_2": {selected_day: [{"dt": 2}]},
        "loc_1": {"city_label": "A", "lat": 1.0, "lon": 2.0},
        "loc_2": {"city_label": "B", "lat": 3.0, "lon": 4.0},
    }
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        ai_weather_service=SimpleNamespace(
            compare_two_locations_forecast_day_with_ai=lambda *a, **k: "summary"
        ),
        main_menu=lambda: types.ReplyKeyboardMarkup(),
        build_ai_compare_date_post_result_keyboard=keyboards.build_ai_compare_date_post_result_keyboard,
    )
    session_store = SimpleNamespace(
        get_state=lambda uid: WAITING_AI_COMPARE_DATE_PICK if uid == user_id else None,
        user_states={user_id: WAITING_AI_COMPARE_DATE_PICK},
        ai_compare_drafts={user_id: draft},
        ai_compare_location_choices={user_id: []},
    )

    handle_ai_compare_callback(
        _call(data=f"aicmp_date_pick:{selected_day}", user_id=user_id),
        ctx=ctx,
        session_store=session_store,
    )

    edit_calls = [c for c in bot.calls if c[0] == "edit_message_text"]
    assert edit_calls, "expected date-choice cleanup via edit_message_text"
    _name, args, kwargs = edit_calls[0]
    assert args[0] == f"✅ Выбрано: {selected_day}"
    assert kwargs.get("reply_markup") is None
    assert session_store.ai_compare_drafts.get(user_id) is draft
    assert user_id not in session_store.user_states
    send_calls = [c for c in bot.calls if c[0] == "send_message"]
    interim = send_calls[0][1][1] if len(send_calls[0][1]) > 1 else send_calls[0][1][0]
    assert "Вторая локация" not in interim
    assert interim == f"Сравниваю прогноз на {selected_day}."
    assert "Обновляю сравнение" not in interim


def test_date_pick_result_message_has_post_result_inline_keyboard():
    bot = _Bot()
    user_id = 8
    day = "03.05"
    draft = {
        "mode": "date",
        "available_days": [day],
        "grouped_1": {day: [{"x": 1}]},
        "grouped_2": {day: [{"x": 2}]},
        "loc_1": {"city_label": "X", "lat": 1.0, "lon": 1.0},
        "loc_2": {"city_label": "Y", "lat": 2.0, "lon": 2.0},
    }
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        ai_weather_service=SimpleNamespace(
            compare_two_locations_forecast_day_with_ai=lambda *a, **k: "out"
        ),
        main_menu=lambda: types.ReplyKeyboardMarkup(),
        build_ai_compare_date_post_result_keyboard=keyboards.build_ai_compare_date_post_result_keyboard,
    )
    session_store = SimpleNamespace(
        get_state=lambda uid: WAITING_AI_COMPARE_DATE_PICK if uid == user_id else None,
        user_states={user_id: WAITING_AI_COMPARE_DATE_PICK},
        ai_compare_drafts={user_id: draft},
        ai_compare_location_choices={},
    )

    handle_ai_compare_callback(
        _call(data=f"aicmp_date_pick:{day}", user_id=user_id),
        ctx=ctx,
        session_store=session_store,
    )

    send_calls = [c for c in bot.calls if c[0] == "send_message"]
    assert len(send_calls) >= 2
    _name, args, kwargs = send_calls[-1]
    body = args[1] if len(args) > 1 else args[0]
    assert body == f"✨ Сравнение локаций на {day}\n\nout"
    assert "Сравнить локации" not in body
    assert "Вывод:" not in body
    markup = kwargs.get("reply_markup")
    assert isinstance(markup, types.InlineKeyboardMarkup)
    buttons = _flat_inline_buttons(markup)
    assert ("📅 Выбрать другую дату", "aicmp_date_another") in buttons
    assert ("⬅️ В меню", "yn_menu") in buttons
    interim = send_calls[0][1][1] if len(send_calls[0][1]) > 1 else send_calls[0][1][0]
    assert "Вторая локация" not in interim
    assert interim == f"Сравниваю прогноз на {day}."
    assert "Обновляю сравнение" not in interim


def test_date_pick_after_date_repick_uses_update_wording():
    bot = _Bot()
    user_id = 11
    day = "02.05"
    draft = {
        "mode": "date",
        "date_repick": True,
        "available_days": [day],
        "grouped_1": {day: [{"x": 1}]},
        "grouped_2": {day: [{"x": 2}]},
        "loc_1": {"city_label": "X", "lat": 1.0, "lon": 1.0},
        "loc_2": {"city_label": "Y", "lat": 2.0, "lon": 2.0},
    }
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        ai_weather_service=SimpleNamespace(
            compare_two_locations_forecast_day_with_ai=lambda *a, **k: "out"
        ),
        main_menu=lambda: types.ReplyKeyboardMarkup(),
        build_ai_compare_date_post_result_keyboard=keyboards.build_ai_compare_date_post_result_keyboard,
    )
    session_store = SimpleNamespace(
        get_state=lambda uid: WAITING_AI_COMPARE_DATE_PICK if uid == user_id else None,
        user_states={user_id: WAITING_AI_COMPARE_DATE_PICK},
        ai_compare_drafts={user_id: draft},
        ai_compare_location_choices={},
    )

    handle_ai_compare_callback(
        _call(data=f"aicmp_date_pick:{day}", user_id=user_id),
        ctx=ctx,
        session_store=session_store,
    )

    send_calls = [c for c in bot.calls if c[0] == "send_message"]
    interim = send_calls[0][1][1] if len(send_calls[0][1]) > 1 else send_calls[0][1][0]
    assert interim == f"Обновляю сравнение на {day}."
    assert "Сравниваю прогноз на" not in interim
    assert "Вторая локация" not in interim
    assert "date_repick" not in draft


def test_date_another_with_valid_draft_resends_date_picker_and_sets_state():
    bot = _Bot()
    user_id = 9
    days = ["01.05", "02.05"]
    draft = {
        "mode": "date",
        "available_days": days,
        "grouped_1": {"01.05": []},
        "grouped_2": {"01.05": []},
        "loc_1": {"city_label": "P", "lat": 1.0, "lon": 1.0},
        "loc_2": {"city_label": "Q", "lat": 2.0, "lon": 2.0},
    }

    def build_days(d):
        kb = types.InlineKeyboardMarkup()
        for x in d:
            kb.add(types.InlineKeyboardButton(text=x, callback_data=f"aicmp_date_pick:{x}"))
        return kb

    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        ai_weather_service=SimpleNamespace(),
        main_menu=lambda: types.ReplyKeyboardMarkup(),
        build_ai_compare_days_keyboard=build_days,
    )
    session_store = SimpleNamespace(
        get_state=lambda uid: None,
        user_states={},
        ai_compare_drafts={user_id: draft},
    )

    handle_ai_compare_callback(_call(data="aicmp_date_another", user_id=user_id), ctx=ctx, session_store=session_store)

    assert draft.get("date_repick") is True
    assert session_store.user_states.get(user_id) == WAITING_AI_COMPARE_DATE_PICK
    send_calls = [c for c in bot.calls if c[0] == "send_message"]
    assert len(send_calls) == 1
    _name, args, kwargs = send_calls[0]
    text = args[1] if len(args) > 1 else args[0]
    assert text == "Выбери дату для сравнения:"
    mk = kwargs["reply_markup"]
    assert isinstance(mk, types.InlineKeyboardMarkup)


def test_date_another_missing_draft_sends_friendly_message_and_clears():
    bot = _Bot()
    user_id = 10
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        ai_weather_service=SimpleNamespace(),
        main_menu=lambda: types.ReplyKeyboardMarkup(),
        build_ai_compare_days_keyboard=lambda d: types.InlineKeyboardMarkup(),
    )
    session_store = SimpleNamespace(
        get_state=lambda uid: None,
        user_states={user_id: "something"},
        ai_compare_drafts={},
        ai_compare_location_choices={},
    )

    handle_ai_compare_callback(_call(data="aicmp_date_another", user_id=user_id), ctx=ctx, session_store=session_store)

    send_calls = [c for c in bot.calls if c[0] == "send_message"]
    assert len(send_calls) == 1
    _name, args, kwargs = send_calls[0]
    text = args[1] if len(args) > 1 else args[0]
    assert "Не нашла предыдущие локации" in text
    assert user_id not in session_store.user_states
