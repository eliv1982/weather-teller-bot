import importlib
import sys
import types

import pytest


class _FakeTeleBot:
    def __init__(self, token):
        self.token = token

    def message_handler(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def callback_query_handler(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def send_message(self, *args, **kwargs):
        return None

    def answer_callback_query(self, *args, **kwargs):
        return None


def _import_bot(monkeypatch):
    telebot_module = types.ModuleType("telebot")
    telebot_module.TeleBot = _FakeTeleBot
    telebot_module.types = types.SimpleNamespace(
        Message=object,
        CallbackQuery=object,
        ReplyKeyboardMarkup=object,
        KeyboardButton=object,
        InlineKeyboardMarkup=object,
        InlineKeyboardButton=object,
        ReplyKeyboardRemove=lambda: "reply-keyboard-remove",
    )
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda: None

    monkeypatch.setenv("BOT_TOKEN", "test-bot-token")
    monkeypatch.setitem(sys.modules, "telebot", telebot_module)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv_module)
    sys.modules.pop("bot", None)
    return importlib.import_module("bot")


def _location_message(*, user_id: int = 1, chat_id: int = 2, lat: float = 55.75, lon: float = 37.61):
    return types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=user_id),
        chat=types.SimpleNamespace(id=chat_id),
        location=types.SimpleNamespace(latitude=lat, longitude=lon),
    )


@pytest.mark.parametrize(
    "state_name",
    ["WAITING_NEW_SAVED_LOCATION_GEO", "WAITING_NEW_SAVED_LOCATION_MENU"],
)
def test_location_message_saved_location_geo_states_use_saved_location_candidate_helper(monkeypatch, state_name):
    bot = _import_bot(monkeypatch)
    calls = []
    monkeypatch.setattr(bot, "get_location_by_coordinates", lambda lat, lon: {"label": "Москва"})
    monkeypatch.setattr(bot, "build_location_label", lambda location, show_coords=False: "Москва")
    monkeypatch.setattr(
        bot,
        "_set_new_saved_location_candidate",
        lambda message, user_id, *, lat, lon, label, ctx, session_store: calls.append(
            {
                "user_id": user_id,
                "lat": lat,
                "lon": lon,
                "label": label,
                "ctx": ctx,
                "session_store": session_store,
            }
        ),
    )

    state = getattr(bot, state_name)
    bot.session_store.user_states[1] = state

    bot.handle_location_message(_location_message())

    assert calls == [
        {
            "user_id": 1,
            "lat": 55.75,
            "lon": 37.61,
            "label": "Москва",
            "ctx": bot.ctx,
            "session_store": bot.session_store,
        }
    ]


@pytest.mark.parametrize(
    ("state_name", "expected_step"),
    [
        ("WAITING_AI_COMPARE_LOC1_METHOD", 1),
        ("WAITING_AI_COMPARE_LOC2_METHOD", 2),
        ("WAITING_AI_COMPARE_LOC1_GEO", 1),
        ("WAITING_AI_COMPARE_LOC2_GEO", 2),
    ],
)
def test_location_message_ai_compare_geo_states_use_compare_location_helper(monkeypatch, state_name, expected_step):
    bot = _import_bot(monkeypatch)
    calls = []
    monkeypatch.setattr(bot, "get_location_by_coordinates", lambda lat, lon: {"label": "Москва"})
    monkeypatch.setattr(bot, "build_location_label", lambda location, show_coords=False: "Москва")
    monkeypatch.setattr(
        bot,
        "_ai_compare_set_location",
        lambda message, user_id, *, step, city_label, lat, lon, ctx, session_store: calls.append(
            {
                "user_id": user_id,
                "step": step,
                "city_label": city_label,
                "lat": lat,
                "lon": lon,
                "ctx": ctx,
                "session_store": session_store,
            }
        ),
    )

    state = getattr(bot, state_name)
    bot.session_store.user_states[1] = state

    bot.handle_location_message(_location_message())

    assert calls == [
        {
            "user_id": 1,
            "step": expected_step,
            "city_label": "Москва",
            "lat": 55.75,
            "lon": 37.61,
            "ctx": bot.ctx,
            "session_store": bot.session_store,
        }
    ]
    assert 1 not in bot.session_store.user_states
