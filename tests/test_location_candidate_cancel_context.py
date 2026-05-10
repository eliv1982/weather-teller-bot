from types import SimpleNamespace

from handlers.callbacks_common import return_to_location_input_context
from handlers.callbacks_compare import handle_compare_location_callback
from handlers.callbacks_current import handle_current_weather_callback
from handlers.callbacks_source_compare import handle_source_compare_callback
from handlers.states import WAITING_COMPARE_CITY_1, WAITING_COMPARE_CITY_2, WAITING_CURRENT_WEATHER_CITY, WAITING_SOURCE_COMPARE_CITY


class _Bot:
    def __init__(self):
        self.calls = []

    def send_message(self, *args, **kwargs):
        self.calls.append(("send_message", args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.calls.append(("answer_callback_query", args, kwargs))


def _call(data: str, *, user_id: int = 1, chat_id: int = 10):
    return SimpleNamespace(
        data=data,
        id="cbq",
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=77),
    )


def test_current_cancel_returns_to_current_weather_input_context():
    bot = _Bot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {"saved_locations": [{"id": "1"}]},
        location_input_menu=lambda has_saved_locations=True: ("location-input", has_saved_locations),
        main_menu=lambda: "main-menu",
    )
    session_store = SimpleNamespace(
        current_location_choices={1: [{"label": "Москва"}]},
        user_states={1: "waiting_current_weather_pick"},
    )

    handle_current_weather_callback(_call("current_cancel"), ctx=ctx, session_store=session_store)

    assert session_store.user_states[1] == WAITING_CURRENT_WEATHER_CITY
    assert bot.calls[-1] == (
        "send_message",
        (10, "Введи название населённого пункта или выбери другой способ ниже:"),
        {"reply_markup": ("location-input", True)},
    )


def test_source_compare_cancel_returns_to_source_compare_location_prompt():
    bot = _Bot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {"saved_locations": [{"id": "1"}]},
        location_input_menu=lambda has_saved_locations=True: ("location-input", has_saved_locations),
        main_menu=lambda: "main-menu",
    )
    session_store = SimpleNamespace(
        source_compare_location_choices={1: [{"label": "Москва"}]},
        user_states={1: "waiting_source_compare_pick"},
    )

    handle_source_compare_callback(
        _call("source_compare_cancel"),
        ctx=ctx,
        session_store=session_store,
        send_source_compare_by_coordinates=lambda *args, **kwargs: None,
        send_source_compare_by_selected_date=lambda *args, **kwargs: None,
        _message_stub_for_chat=lambda chat_id: SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    assert session_store.user_states[1] == WAITING_SOURCE_COMPARE_CITY
    assert bot.calls[-1] == (
        "send_message",
        (10, "Введи название населённого пункта или выбери другой способ ниже:"),
        {"reply_markup": ("location-input", True)},
    )


def test_compare_cancel_from_first_location_returns_to_first_prompt():
    bot = _Bot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {},
        main_menu=lambda: "main-menu",
    )
    session_store = SimpleNamespace(
        compare_location_choices={1: {"step": 1, "locations": [{"label": "Москва"}]}},
        compare_drafts={},
        user_states={1: "waiting_compare_location_pick"},
    )

    handle_compare_location_callback(
        _call("compare_cancel"),
        ctx=ctx,
        session_store=session_store,
        WAITING_COMPARE_CITY_2=WAITING_COMPARE_CITY_2,
        complete_compare_two_locations=lambda *args, **kwargs: None,
    )

    assert session_store.user_states[1] == WAITING_COMPARE_CITY_1
    assert bot.calls[-1] == (
        "send_message",
        (10, "Введи название первой локации."),
        {"reply_markup": None},
    )


def test_compare_cancel_from_second_location_returns_to_second_prompt():
    bot = _Bot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {},
        main_menu=lambda: "main-menu",
    )
    session_store = SimpleNamespace(
        compare_location_choices={1: {"step": 2, "locations": [{"label": "Москва"}]}},
        compare_drafts={1: {"coordinates_1": (1.0, 2.0), "city_1_label": "Москва"}},
        user_states={1: "waiting_compare_location_pick"},
    )

    handle_compare_location_callback(
        _call("compare_cancel"),
        ctx=ctx,
        session_store=session_store,
        WAITING_COMPARE_CITY_2=WAITING_COMPARE_CITY_2,
        complete_compare_two_locations=lambda *args, **kwargs: None,
    )

    assert session_store.user_states[1] == WAITING_COMPARE_CITY_2
    assert session_store.compare_drafts[1]["city_1_label"] == "Москва"
    assert bot.calls[-1] == (
        "send_message",
        (10, "Введи название второй локации."),
        {"reply_markup": None},
    )


def test_unknown_context_cancel_falls_back_to_main_menu():
    bot = _Bot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {},
        main_menu=lambda: "main-menu",
    )
    session_store = SimpleNamespace(user_states={1: "some-state"})

    return_to_location_input_context(
        10,
        1,
        ctx=ctx,
        session_store=session_store,
        target_state=None,
    )

    assert 1 not in session_store.user_states
    assert bot.calls[-1] == (
        "send_message",
        (10, "Выбор отменён."),
        {"reply_markup": "main-menu"},
    )
