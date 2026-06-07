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
    send_source_compare_by_coordinates,
    send_source_compare_by_selected_date,
    start_source_compare_flow,
    start_source_compare_mode_flow,
)
from flows_source_compare import (
    send_source_compare_by_coordinates as direct_send_source_compare_by_coordinates,
    send_source_compare_by_selected_date as direct_send_source_compare_by_selected_date,
    start_source_compare_flow as direct_start_source_compare_flow,
    start_source_compare_mode_flow as direct_start_source_compare_mode_flow,
)
from session_store import SessionStore


class _FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


def _message(chat_id=123, user_id=7):
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id), from_user=SimpleNamespace(id=user_id))


def test_source_compare_flow_functions_are_importable_from_flows_and_flows_source_compare():
    assert callable(start_source_compare_flow)
    assert callable(start_source_compare_mode_flow)
    assert callable(send_source_compare_by_coordinates)
    assert callable(send_source_compare_by_selected_date)
    assert callable(direct_start_source_compare_flow)
    assert callable(direct_start_source_compare_mode_flow)
    assert callable(direct_send_source_compare_by_coordinates)
    assert callable(direct_send_source_compare_by_selected_date)


def test_start_source_compare_flow_works_via_direct_flows_source_compare_import():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        source_compare_mode_menu=lambda: "source-compare-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_source_compare_city"
    session_store.source_compare_drafts[7] = {"mode": "today"}
    session_store.source_compare_location_choices[7] = [{"label": "Москва"}]

    direct_start_source_compare_flow(_message(), ctx=ctx, session_store=session_store)

    assert session_store.user_states[7] == "source_compare_menu"
    assert 7 not in session_store.source_compare_drafts
    assert 7 not in session_store.source_compare_location_choices
    assert bot.messages == [
        {"chat_id": 123, "text": "Выбери режим сравнения источников.", "reply_markup": "source-compare-menu"}
    ]


def test_send_source_compare_by_selected_date_works_via_direct_flows_source_compare_import():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        format_source_compare_response=lambda city, ow, om, title=None: (
            f"compare {city} {ow['dominant_description']} {om['dominant_description']} {title}"
        ),
        build_source_compare_date_post_result_keyboard=lambda: "post-result-keyboard",
        main_menu=lambda: "main-menu",
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_source_compare_date_pick"
    session_store.source_compare_drafts[7] = {
        "mode": "date",
        "city_label": "Москва",
        "lat": 55.75,
        "lon": 37.61,
    }

    result = direct_send_source_compare_by_selected_date(
        _message(),
        7,
        "11.05",
        ctx=ctx,
        session_store=session_store,
        sources_by_date_comparer=lambda lat, lon, city, selected_day: {
            "ok": True,
            "title": f"🔎 Сравнение прогнозов на {selected_day}",
            "openweather": {"dominant_description": "ясно"},
            "open_meteo": {"dominant_description": "облачно"},
        },
    )

    assert result is True
    assert 7 not in session_store.user_states
    assert session_store.source_compare_drafts[7]["selected_day"] == "11.05"
    assert bot.messages == [
        {
            "chat_id": 123,
            "text": "compare Москва ясно облачно 🔎 Сравнение прогнозов на 11.05",
            "reply_markup": "post-result-keyboard",
        }
    ]
