import importlib
import sys
import types

from handlers import ai_compare
from handlers import callbacks_locations


def test_ai_compare_module_direct_import_exports_are_callable():
    sample_payload = {
        "city_label": "Москва",
        "min_temp": 5,
        "max_temp": 12,
        "dominant_description": "облачно",
        "precipitation_signal": {"max_pop": 0.2},
        "wind_signal": {"avg_speed": 3, "max_speed": 6},
    }

    assert callable(ai_compare.start_ai_compare_flow)
    assert callable(ai_compare.handle_ai_compare_text)
    assert callable(ai_compare._ai_compare_after_two_locations)
    assert callable(ai_compare._ai_compare_day_payload)
    assert ai_compare.format_ai_compare_day_summary_message(sample_payload, "01.05", 1).strip()
    assert ai_compare.normalize_location_name("  ДоМ  —   Тольятти  ") == "тольятти"


def test_runtime_modules_import_ai_compare_directly(monkeypatch):
    assert callbacks_locations._ai_compare_set_location is ai_compare._ai_compare_set_location
    assert callbacks_locations._ai_compare_reset is ai_compare._ai_compare_reset
    assert callbacks_locations._ai_compare_day_payload is ai_compare._ai_compare_day_payload

    telebot_module = types.ModuleType("telebot")
    telebot_module.TeleBot = lambda token: types.SimpleNamespace(
        message_handler=lambda *args, **kwargs: (lambda func: func),
        callback_query_handler=lambda *args, **kwargs: (lambda func: func),
        send_message=lambda *args, **kwargs: None,
        answer_callback_query=lambda *args, **kwargs: None,
    )
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
    bot = importlib.import_module("bot")

    assert bot.start_ai_compare_flow is ai_compare.start_ai_compare_flow
    assert bot._ai_compare_set_location is ai_compare._ai_compare_set_location
