import importlib
import os
import sys
import types


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


def test_weather_menu_button_routes_to_source_compare(monkeypatch):
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
    bot = importlib.import_module("bot")

    calls = []
    monkeypatch.setattr(bot, "start_source_compare_flow", lambda message: calls.append(message.text))
    message = types.SimpleNamespace(text="🔎 Сверить источники", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_menu_buttons(message)

    assert calls == ["🔎 Сверить источники"]


def test_weather_menu_button_routes_current_weather_via_new_visible_label(monkeypatch):
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
    bot = importlib.import_module("bot")

    calls = []
    monkeypatch.setattr(bot, "start_current_weather_flow", lambda message: calls.append(message.text))
    message = types.SimpleNamespace(text="🌡 Погода сейчас", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_menu_buttons(message)

    assert calls == ["🌡 Погода сейчас"]


def test_weather_menu_button_routes_today_forecast_to_forecast_flow_not_current(monkeypatch):
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
    bot = importlib.import_module("bot")

    today_calls = []
    current_calls = []
    monkeypatch.setattr(bot, "start_today_forecast_flow", lambda message: today_calls.append(message.text))
    monkeypatch.setattr(bot, "start_current_weather_flow", lambda message: current_calls.append(message.text))
    message = types.SimpleNamespace(text="☀️ Прогноз на сегодня", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_menu_buttons(message)

    assert today_calls == ["☀️ Прогноз на сегодня"]
    assert current_calls == []
