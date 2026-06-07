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
    send_forecast_by_coordinates,
    send_today_forecast_by_coordinates,
    send_tomorrow_forecast_by_coordinates,
    show_forecast_days_message,
    start_forecast_flow,
    start_today_forecast_flow,
    start_tomorrow_forecast_flow,
)
from flows_forecast import (
    send_forecast_by_coordinates as direct_send_forecast_by_coordinates,
    send_today_forecast_by_coordinates as direct_send_today_forecast_by_coordinates,
    send_tomorrow_forecast_by_coordinates as direct_send_tomorrow_forecast_by_coordinates,
    show_forecast_days_message as direct_show_forecast_days_message,
    start_forecast_flow as direct_start_forecast_flow,
    start_today_forecast_flow as direct_start_today_forecast_flow,
    start_tomorrow_forecast_flow as direct_start_tomorrow_forecast_flow,
)
from forecast_service import group_forecast_by_day
from session_store import SessionStore


class _FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


def _message(chat_id=123, user_id=7):
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id), from_user=SimpleNamespace(id=user_id))


def test_forecast_flow_functions_are_importable_from_flows_and_flows_forecast():
    assert callable(send_forecast_by_coordinates)
    assert callable(send_today_forecast_by_coordinates)
    assert callable(send_tomorrow_forecast_by_coordinates)
    assert callable(show_forecast_days_message)
    assert callable(start_forecast_flow)
    assert callable(start_today_forecast_flow)
    assert callable(start_tomorrow_forecast_flow)
    assert callable(direct_send_forecast_by_coordinates)
    assert callable(direct_send_today_forecast_by_coordinates)
    assert callable(direct_send_tomorrow_forecast_by_coordinates)
    assert callable(direct_show_forecast_days_message)
    assert callable(direct_start_forecast_flow)
    assert callable(direct_start_today_forecast_flow)
    assert callable(direct_start_tomorrow_forecast_flow)


def test_send_forecast_by_coordinates_works_via_direct_flows_forecast_import():
    forecast_items = [
        {"dt_txt": "2026-05-02 12:00:00", "main": {"temp": 10}, "weather": [{"description": "ясно"}]},
        {"dt_txt": "2026-05-02 15:00:00", "main": {"temp": 11}, "weather": [{"description": "облачно"}]},
        {"dt_txt": "2026-05-03 12:00:00", "main": {"temp": 15}, "weather": [{"description": "дождь"}]},
    ]
    bot = _FakeBot()
    saved_users = {}
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
        get_forecast_5d3h=lambda lat, lon: forecast_items,
        group_forecast_by_day=group_forecast_by_day,
        get_location_by_coordinates=lambda lat, lon: None,
        build_location_label=lambda location, show_coords=False: "Москва",
        load_user=lambda user_id: {},
        save_user=lambda user_id, data: saved_users.__setitem__(user_id, data),
        main_menu=lambda: "main-menu",
        build_forecast_days_keyboard=lambda days: {"days": days},
    )
    session_store = SessionStore()
    session_store.user_states[7] = "waiting_forecast_city"

    result = direct_send_forecast_by_coordinates(
        _message(),
        7,
        55.75,
        37.61,
        "Москва",
        save_location=True,
        preferred_city_label="Москва",
        ctx=ctx,
        session_store=session_store,
    )

    assert result is True
    assert session_store.forecast_cache[7]["city"] == "Москва"
    assert list(session_store.forecast_cache[7]["grouped"].keys()) == ["02.05", "03.05"]
    assert 7 not in session_store.user_states
    assert saved_users[7]["city"] == "Москва"
    assert [message["text"] for message in bot.messages] == [
        "Прогноз готов.",
        "Выбери день прогноза для Москва:",
    ]
    assert bot.messages[0]["reply_markup"] is not None
    assert bot.messages[1]["reply_markup"] == {"days": ["02.05", "03.05"]}
