import importlib
import sys
import types


class _KeyboardButton:
    def __init__(self, text, **kwargs):
        self.text = text
        self.kwargs = kwargs


class _ReplyKeyboardMarkup:
    def __init__(self, **kwargs):
        self.keyboard = []
        self.kwargs = kwargs

    def row(self, *buttons):
        self.keyboard.append(list(buttons))


class _InlineKeyboardButton:
    def __init__(self, text, callback_data=None, **kwargs):
        self.text = text
        self.callback_data = callback_data
        self.kwargs = kwargs


class _InlineKeyboardMarkup:
    def __init__(self, **kwargs):
        self.keyboard = []
        self.kwargs = kwargs

    def row(self, *buttons):
        self.keyboard.append(list(buttons))

    def add(self, *buttons):
        self.keyboard.append(list(buttons))


def _load_keyboards(monkeypatch):
    telebot_module = types.ModuleType("telebot")
    telebot_module.types = types.SimpleNamespace(
        KeyboardButton=_KeyboardButton,
        ReplyKeyboardMarkup=_ReplyKeyboardMarkup,
        InlineKeyboardButton=_InlineKeyboardButton,
        InlineKeyboardMarkup=_InlineKeyboardMarkup,
    )
    monkeypatch.setitem(sys.modules, "telebot", telebot_module)
    sys.modules.pop("keyboards", None)
    return importlib.import_module("keyboards")


def _button_texts(markup):
    return [button.text for row in markup.keyboard for button in row]


def _button_rows(markup):
    return [[button.text for button in row] for row in markup.keyboard]


def test_main_menu_contains_grouped_top_level_sections(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    assert _button_texts(keyboards.main_menu()) == [
        "🌦 Прогноз погоды",
        "📍 Локации",
        "🔔 Подписки",
        "ℹ️ Помощь",
    ]


def test_weather_menu_groups_actions_two_per_row(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    assert _button_rows(keyboards.weather_menu()) == [
        ["🌡 Погода сейчас", "☀️ Прогноз на сегодня"],
        ["🌤 Прогноз на завтра", "📅 Прогноз на 5 дней"],
        ["🧭 Расширенные данные", "📅 История погоды"],
        ["🔎 Сравнить источники"],
        ["⬅️ В меню"],
    ]
    assert keyboards.weather_menu().kwargs.get("one_time_keyboard") is False
    assert keyboards.weather_menu().kwargs.get("is_persistent") is True


def test_locations_menu_contains_expected_submenu_buttons(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    assert _button_texts(keyboards.locations_menu()) == [
        "📋 Показать мои локации",
        "⚖️ Сравнить локации",
        "⬅️ В меню",
    ]


def test_saved_locations_management_menu_contains_expected_actions(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    assert _button_texts(keyboards.saved_locations_management_menu()) == [
        "➕ Добавить локацию",
        "🗑 Удалить локацию",
        "✏️ Изменить локацию",
        "⚖️ Сравнить локации",
        "⬅️ В меню",
    ]


def test_compare_mode_menu_uses_emoji_labels(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    assert _button_texts(keyboards.ai_compare_mode_menu()) == [
        "⚖️ Сравнить сейчас",
        "📅 Сравнить на дату",
        "⬅️ Назад",
    ]


def test_source_compare_mode_menu_groups_modes_cleanly(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    assert _button_rows(keyboards.source_compare_mode_menu()) == [
        ["🌡 Сейчас", "☀️ Сегодня"],
        ["🌤 Завтра", "📅 На дату"],
        ["⬅️ Назад"],
    ]
    assert keyboards.source_compare_mode_menu().kwargs.get("one_time_keyboard") is False
    assert keyboards.source_compare_mode_menu().kwargs.get("is_persistent") is True


def test_history_date_keyboard_contains_presets_and_menu(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    buttons = [
        (button.text, button.callback_data)
        for row in keyboards.build_history_date_keyboard().keyboard
        for button in row
    ]

    assert buttons == [
        ("Вчера", "history_date_preset:yesterday"),
        ("7 дней назад", "history_date_preset:7d"),
        ("30 дней назад", "history_date_preset:30d"),
        ("Выбрать дату", "history_date_custom"),
        ("⬅️ В меню", "history_menu"),
    ]
