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

from flows import send_details_by_coordinates, start_current_weather_flow, start_details_flow
from flows_current import (
    send_details_by_coordinates as direct_send_details_by_coordinates,
    start_current_weather_flow as direct_start_current_weather_flow,
    start_details_flow as direct_start_details_flow,
)
from session_store import SessionStore


class _FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


def _message(chat_id=123, user_id=7):
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id), from_user=SimpleNamespace(id=user_id))


def test_current_flow_functions_are_importable_from_flows_and_flows_current():
    assert callable(start_current_weather_flow)
    assert callable(start_details_flow)
    assert callable(send_details_by_coordinates)
    assert callable(direct_start_current_weather_flow)
    assert callable(direct_start_details_flow)
    assert callable(direct_send_details_by_coordinates)


def test_start_current_weather_flow_works_via_direct_flows_current_import():
    bot = _FakeBot()
    ctx = SimpleNamespace(
        bot=bot,
        load_user=lambda user_id: {"saved_locations": [{"id": "loc-1"}]},
        location_input_menu=lambda has_saved_locations=False: {"has_saved_locations": has_saved_locations},
    )
    session_store = SessionStore()
    session_store.user_states[7] = "old-state"
    session_store.current_location_choices[7] = [{"label": "Москва"}]
    session_store.current_favorite_drafts[7] = {"city": "Москва"}

    direct_start_current_weather_flow(_message(), ctx=ctx, session_store=session_store)

    assert session_store.user_states[7] == "waiting_current_weather_city"
    assert 7 not in session_store.current_location_choices
    assert 7 not in session_store.current_favorite_drafts
    assert bot.messages == [
        {
            "chat_id": 123,
            "text": "Введи название населённого пункта или выбери другой способ ниже:",
            "reply_markup": {"has_saved_locations": True},
        }
    ]


def test_send_details_by_coordinates_works_via_direct_flows_current_import():
    bot = _FakeBot()
    saved_users = {}
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
        get_current_weather=lambda lat, lon: {"temp": 22},
        get_air_pollution=lambda lat, lon: {"pm2_5": 12},
        get_location_by_coordinates=lambda lat, lon: None,
        build_location_label=lambda location, show_coords=False: "Москва",
        load_user=lambda user_id: {},
        save_user=lambda user_id, data: saved_users.__setitem__(user_id, data),
        format_details_response=lambda city, weather, air_components: f"details {city} {weather['temp']} {air_components['pm2_5']}",
        main_menu=lambda: "main-menu",
        build_ai_action_keyboard=lambda text, callback_data: {"text": text, "callback_data": callback_data},
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_details_city"
    session_store.details_saved_drafts[7] = {"city": "Старое"}
    session_store.details_location_choices[7] = [{"label": "Москва"}]
    session_store.generate_ai_snapshot_id = lambda user_id: "snap-1"
    cleanup_calls = []
    session_store.cleanup_ai_snapshots = lambda: cleanup_calls.append("called")

    result = direct_send_details_by_coordinates(
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
    assert 7 not in session_store.user_states
    assert 7 not in session_store.details_saved_drafts
    assert 7 not in session_store.details_location_choices
    assert saved_users[7]["city"] == "Москва"
    assert session_store.ai_details_snapshots["snap-1"]["user_id"] == 7
    assert session_store.ai_details_snapshots["snap-1"]["city_label"] == "Москва"
    assert session_store.ai_details_snapshots["snap-1"]["weather"] == {"temp": 22}
    assert session_store.ai_details_snapshots["snap-1"]["air_components"] == {"pm2_5": 12}
    assert cleanup_calls == ["called"]
    assert [message["text"] for message in bot.messages] == [
        "details Москва 22 12",
        "💡 Хочешь простое пояснение данных?",
    ]
    assert bot.messages[-1]["reply_markup"] == {
        "text": "💡 Пояснить данные",
        "callback_data": "ai_details_explain:snap-1",
    }
