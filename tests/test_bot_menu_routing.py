import importlib
import os
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
    message = types.SimpleNamespace(text="🔎 Сравнить источники", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_menu_buttons(message)

    assert calls == ["🔎 Сравнить источники"]


def test_weather_menu_button_routes_to_history(monkeypatch):
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
    monkeypatch.setattr(bot, "start_weather_history_flow", lambda message: calls.append(message.text))
    message = types.SimpleNamespace(text="📅 История погоды", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_menu_buttons(message)

    assert calls == ["📅 История погоды"]


def test_source_compare_menu_mode_button_sets_current_mode_and_asks_for_location(monkeypatch):
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
    monkeypatch.setattr(bot, "start_source_compare_mode_flow", lambda message, mode: calls.append((message.text, mode)))
    bot.session_store.user_states[1] = bot.SOURCE_COMPARE_MENU
    message = types.SimpleNamespace(text="🌡 Сейчас", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_menu_buttons(message)

    assert calls == [("🌡 Сейчас", "current")]


def test_unknown_text_in_source_compare_menu_reshows_same_keyboard(monkeypatch):
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

    sent = []
    monkeypatch.setattr(bot.bot, "send_message", lambda *args, **kwargs: sent.append((args, kwargs)))
    monkeypatch.setattr(bot, "source_compare_mode_menu", lambda: "source-compare-menu")
    bot.session_store.user_states[1] = bot.SOURCE_COMPARE_MENU
    message = types.SimpleNamespace(text="непонятно", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_unknown_text(message)

    assert sent == [((2, "Выбери режим сравнения источников."), {"reply_markup": "source-compare-menu"})]


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


def test_unknown_text_in_weather_menu_reshows_same_keyboard(monkeypatch):
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

    sent = []
    monkeypatch.setattr(bot.bot, "send_message", lambda *args, **kwargs: sent.append((args, kwargs)))
    monkeypatch.setattr(bot, "weather_menu", lambda: "weather-menu")
    bot.session_store.user_states[1] = bot.WEATHER_MENU
    message = types.SimpleNamespace(text="абракадабра", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_unknown_text(message)

    assert sent == [((2, "Выбери раздел в меню ниже."), {"reply_markup": "weather-menu"})]


def test_main_menu_weather_button_sets_weather_menu_state_and_resends_same_keyboard(monkeypatch):
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

    sent = []
    monkeypatch.setattr(bot.bot, "send_message", lambda *args, **kwargs: sent.append((args, kwargs)))
    monkeypatch.setattr(bot.ctx, "weather_menu", lambda: "weather-menu")
    monkeypatch.setattr(bot, "weather_menu", lambda: "weather-menu")

    open_message = types.SimpleNamespace(text="🌦 Прогноз погоды", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))
    text_message = types.SimpleNamespace(text="любой текст", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_menu_buttons(open_message)
    assert bot.session_store.get_state(1) == bot.WEATHER_MENU

    bot.handle_unknown_text(text_message)

    assert sent == [
        ((2, "Выбери раздел в меню ниже."), {"reply_markup": "weather-menu"}),
        ((2, "Выбери раздел в меню ниже."), {"reply_markup": "weather-menu"}),
    ]


@pytest.mark.parametrize(
    ("state_name", "handler_name"),
    [
        ("WAITING_CURRENT_WEATHER_CITY", "handle_current_text"),
        ("WAITING_TODAY_FORECAST_CITY", "handle_forecast_text"),
        ("WAITING_TOMORROW_FORECAST_CITY", "handle_forecast_text"),
        ("WAITING_FORECAST_CITY", "handle_forecast_text"),
        ("WAITING_DETAILS_CITY", "handle_details_text"),
        ("WAITING_SOURCE_COMPARE_CITY", "handle_source_compare_text"),
        ("WAITING_COMPARE_CITY_1", "handle_compare_text"),
    ],
)
def test_city_text_states_still_dispatch_to_location_handlers(monkeypatch, state_name, handler_name):
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

    called = []

    def _handler(*args, **kwargs):
        called.append(args[2])
        return True

    for candidate in (
        "handle_locations_text",
        "handle_current_text",
        "handle_details_text",
        "handle_forecast_text",
        "handle_source_compare_text",
        "handle_alerts_text",
        "handle_compare_text",
    ):
        monkeypatch.setattr(bot, candidate, lambda *args, **kwargs: False)
    monkeypatch.setattr(bot, handler_name, _handler)
    monkeypatch.setattr(bot.bot, "send_message", lambda *args, **kwargs: None)

    state = getattr(bot, state_name)
    bot.session_store.user_states[1] = state
    message = types.SimpleNamespace(text="Москва", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_unknown_text(message)

    assert called == [state]


def test_valid_source_compare_button_does_not_trigger_unknown_command_fallback(monkeypatch):
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
    sent = []
    monkeypatch.setattr(bot, "start_source_compare_flow", lambda message: calls.append(message.text))
    monkeypatch.setattr(bot.bot, "send_message", lambda *args, **kwargs: sent.append((args, kwargs)))
    message = types.SimpleNamespace(text="🔎 Сравнить источники", from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=2))

    bot.handle_menu_buttons(message)
    bot.handle_unknown_text(message)

    assert calls == ["🔎 Сравнить источники"]
    assert all("Не понял команду" not in args[1] for args, _kwargs in sent if len(args) > 1)
