from types import SimpleNamespace

from handlers.callbacks_locations import handle_ai_compare_callback
from handlers.locations import handle_locations_text
from handlers.states import (
    WAITING_AI_COMPARE_LOC1_COORDS,
    WAITING_AI_COMPARE_LOC1_METHOD,
    WAITING_AI_COMPARE_LOC1_SAVED_PICK,
    WAITING_AI_COMPARE_LOC2_COORDS,
)


class _Bot:
    def __init__(self):
        self.calls = []

    def send_message(self, *args, **kwargs):
        self.calls.append(("send_message", args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.calls.append(("answer_callback_query", args, kwargs))

    def edit_message_text(self, *args, **kwargs):
        self.calls.append(("edit_message_text", args, kwargs))


def test_compare_manual_single_location_confirms_selection(monkeypatch):
    bot = _Bot()
    monkeypatch.setattr(
        "handlers.ai_compare.find_locations_with_assist",
        lambda query, scenario, ctx: {"locations": [{"label": "Москва", "lat": 55.75, "lon": 37.61}]},
    )
    ctx = SimpleNamespace(
        bot=bot,
        build_geocode_item_with_disambiguated_label=lambda locations, index: locations[index],
        build_location_label=lambda item, show_coords=False: item.get("label"),
        ai_compare_location_method_menu=lambda: "method-menu",
    )
    session_store = SimpleNamespace(
        ai_compare_drafts={1: {"mode": "current"}},
        ai_compare_location_choices={},
        user_states={1: WAITING_AI_COMPARE_LOC1_METHOD},
    )
    message = SimpleNamespace(text="Москва", chat=SimpleNamespace(id=100))

    handled = handle_locations_text(message, 1, WAITING_AI_COMPARE_LOC1_METHOD, ctx=ctx, session_store=session_store)

    assert handled is True
    assert bot.calls[0] == ("send_message", (100, "✅ Выбрано: Москва"), {})
    assert bot.calls[1] == ("send_message", (100, "Теперь выбери вторую локацию."), {"reply_markup": "method-menu"})


def test_compare_coordinate_selection_confirms_selection(monkeypatch):
    bot = _Bot()
    monkeypatch.setattr("handlers.ai_compare._ai_compare_after_two_locations", lambda *args, **kwargs: True)
    ctx = SimpleNamespace(
        bot=bot,
        get_location_by_coordinates=lambda lat, lon: {"label": "Координатная точка"},
        build_location_label=lambda item, show_coords=False: item.get("label"),
    )
    session_store = SimpleNamespace(
        ai_compare_drafts={
            1: {
                "mode": "date",
                "loc_1": {"city_label": "Москва", "lat": 55.75, "lon": 37.61},
            }
        },
        ai_compare_location_choices={},
        user_states={1: WAITING_AI_COMPARE_LOC2_COORDS},
    )
    message = SimpleNamespace(text="55.5789, 37.9051", chat=SimpleNamespace(id=100))

    handled = handle_locations_text(message, 1, WAITING_AI_COMPARE_LOC2_COORDS, ctx=ctx, session_store=session_store)

    assert handled is True
    assert bot.calls[0] == ("send_message", (100, "✅ Выбрано: Координатная точка"), {})
    assert bot.calls[1] == ("send_message", (100, "Сравниваю погоду."), {})


def test_compare_saved_location_callback_marks_selected_choice(monkeypatch):
    bot = _Bot()
    call = SimpleNamespace(
        id="callback-id",
        data="aicmp_saved_pick:1:home",
        from_user=SimpleNamespace(id=77),
        message=SimpleNamespace(chat=SimpleNamespace(id=123), message_id=456),
    )
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {
            "saved_locations": [{"id": "home", "label": "Дом", "lat": 55.75, "lon": 37.61}]
        },
        ai_compare_location_method_menu=lambda: "method-menu",
    )
    session_store = SimpleNamespace(
        get_state=lambda user_id: WAITING_AI_COMPARE_LOC1_SAVED_PICK,
        user_states={77: WAITING_AI_COMPARE_LOC1_SAVED_PICK},
        ai_compare_drafts={77: {"mode": "current"}},
        ai_compare_location_choices={},
    )

    handle_ai_compare_callback(call, ctx=ctx, session_store=session_store)

    assert ("answer_callback_query", ("callback-id",), {}) in bot.calls
    assert (
        "edit_message_text",
        ("✅ Выбрано: Дом",),
        {"chat_id": 123, "message_id": 456, "reply_markup": None},
    ) in bot.calls
    assert (
        "send_message",
        (123, "Теперь выбери вторую локацию."),
        {"reply_markup": "method-menu"},
    ) in bot.calls
