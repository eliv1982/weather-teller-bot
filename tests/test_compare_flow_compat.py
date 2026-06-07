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

from flows import complete_compare_two_locations, start_compare_flow
from flows_compare import (
    complete_compare_two_locations as direct_complete_compare_two_locations,
    start_compare_flow as direct_start_compare_flow,
)
from session_store import SessionStore


class _FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


def _message(chat_id=123, user_id=7):
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id), from_user=SimpleNamespace(id=user_id))


def test_compare_flow_functions_are_importable_from_flows_and_flows_compare():
    assert callable(start_compare_flow)
    assert callable(complete_compare_two_locations)
    assert callable(direct_start_compare_flow)
    assert callable(direct_complete_compare_two_locations)


def test_start_compare_flow_works_via_direct_flows_compare_import():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_compare_city_2"
    session_store.compare_drafts[7] = {"city_1_label": "Старое"}
    session_store.compare_location_choices[7] = {"step": 2, "locations": [{"label": "Москва"}]}

    direct_start_compare_flow(_message(), ctx=ctx, session_store=session_store)

    assert session_store.user_states[7] == "waiting_compare_city_1"
    assert 7 not in session_store.compare_drafts
    assert 7 not in session_store.compare_location_choices
    assert bot.messages == [
        {"chat_id": 123, "text": "Введи первый населённый пункт для сравнения.", "reply_markup": None}
    ]


def test_complete_compare_two_locations_works_via_direct_flows_compare_import():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
        get_current_weather=lambda lat, lon: {"temp": lat + lon},
        format_compare_response=lambda city_1, weather_1, city_2, weather_2: (
            f"compare {city_1} {weather_1['temp']} {city_2} {weather_2['temp']}"
        ),
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_compare_city_2"
    session_store.compare_drafts[7] = {"coordinates_1": (1.0, 2.0)}
    session_store.compare_location_choices[7] = {"step": 2, "locations": [{"label": "Москва"}]}

    direct_complete_compare_two_locations(
        123,
        7,
        1.0,
        2.0,
        "Москва",
        3.0,
        4.0,
        "Тула",
        ctx=ctx,
        session_store=session_store,
    )

    assert 7 not in session_store.user_states
    assert 7 not in session_store.compare_drafts
    assert 7 not in session_store.compare_location_choices
    assert bot.messages == [
        {
            "chat_id": 123,
            "text": "compare Москва 3.0 Тула 7.0",
            "reply_markup": "main-menu",
        }
    ]
