from types import SimpleNamespace

from handlers.callbacks_current import handle_current_weather_callback
from handlers.callbacks_common import mark_location_choice_selected


class _Bot:
    def __init__(self, *, edit_error=None, markup_error=None, delete_error=None):
        self.edit_error = edit_error
        self.markup_error = markup_error
        self.delete_error = delete_error
        self.calls = []

    def edit_message_text(self, *args, **kwargs):
        self.calls.append(("edit_message_text", args, kwargs))
        if self.edit_error:
            raise self.edit_error

    def edit_message_reply_markup(self, *args, **kwargs):
        self.calls.append(("edit_message_reply_markup", args, kwargs))
        if self.markup_error:
            raise self.markup_error

    def delete_message(self, *args, **kwargs):
        self.calls.append(("delete_message", args, kwargs))
        if self.delete_error:
            raise self.delete_error

    def answer_callback_query(self, *args, **kwargs):
        self.calls.append(("answer_callback_query", args, kwargs))


def _call():
    return SimpleNamespace(
        message=SimpleNamespace(
            chat=SimpleNamespace(id=123),
            message_id=456,
        )
    )


def test_mark_location_choice_selected_edits_message_and_removes_keyboard():
    bot = _Bot()
    ctx = SimpleNamespace(bot=bot)

    mark_location_choice_selected(_call(), ctx, "Москва")

    assert bot.calls == [
        (
            "edit_message_text",
            ("✅ Выбрано: Москва",),
            {"chat_id": 123, "message_id": 456, "reply_markup": None},
        )
    ]


def test_mark_location_choice_selected_falls_back_to_remove_reply_markup():
    bot = _Bot(edit_error=RuntimeError("edit failed"))
    ctx = SimpleNamespace(bot=bot)

    mark_location_choice_selected(_call(), ctx, "Москва")

    assert bot.calls[0][0] == "edit_message_text"
    assert bot.calls[1] == (
        "edit_message_reply_markup",
        (),
        {"chat_id": 123, "message_id": 456, "reply_markup": None},
    )


def test_mark_location_choice_selected_falls_back_to_delete_message():
    bot = _Bot(edit_error=RuntimeError("edit failed"), markup_error=RuntimeError("markup failed"))
    ctx = SimpleNamespace(bot=bot)

    mark_location_choice_selected(_call(), ctx, "Москва")

    assert [item[0] for item in bot.calls] == [
        "edit_message_text",
        "edit_message_reply_markup",
        "delete_message",
    ]
    assert bot.calls[2] == ("delete_message", (123, 456), {})


def test_mark_location_choice_selected_ignores_missing_message():
    bot = _Bot()
    ctx = SimpleNamespace(bot=bot)

    mark_location_choice_selected(SimpleNamespace(message=None), ctx, "Москва")

    assert bot.calls == []


def test_mark_location_choice_selected_never_raises_if_cleanup_fails():
    bot = _Bot(
        edit_error=RuntimeError("edit failed"),
        markup_error=RuntimeError("markup failed"),
        delete_error=RuntimeError("delete failed"),
    )
    ctx = SimpleNamespace(bot=bot)

    mark_location_choice_selected(_call(), ctx, "Москва")

    assert [item[0] for item in bot.calls] == [
        "edit_message_text",
        "edit_message_reply_markup",
        "delete_message",
    ]


def test_current_pick_callback_marks_choice_message_selected():
    bot = _Bot()
    call = _call()
    call.id = "callback-id"
    call.data = "current_pick:0"
    call.from_user = SimpleNamespace(id=77)
    completed = []
    location = {"label": "Москва", "lat": 55.75, "lon": 37.61}
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        build_geocode_item_with_disambiguated_label=lambda choices, index: choices[index],
        build_location_label=lambda item, show_coords=False: item.get("label", ""),
        complete_current_weather_from_location=lambda *args, **kwargs: completed.append((args, kwargs)),
        load_user=lambda user_id: {},
        save_user=lambda user_id, user_data: None,
    )
    session_store = SimpleNamespace(
        user_states={77: "waiting_current_pick"},
        current_location_choices={77: [location]},
        ai_current_snapshots={},
        generate_ai_snapshot_id=lambda: "snapshot-id",
        cleanup_ai_snapshots=lambda user_id: None,
    )

    handle_current_weather_callback(call, ctx=ctx, session_store=session_store)

    assert [item[0] for item in bot.calls][:2] == [
        "answer_callback_query",
        "edit_message_text",
    ]
    assert bot.calls[1] == (
        "edit_message_text",
        ("✅ Выбрано: Москва",),
        {"chat_id": 123, "message_id": 456, "reply_markup": None},
    )
    assert completed
