import importlib
import sys
import types
from datetime import date


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


def test_history_section_keyboard_contains_daily_and_climate_modes(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    buttons = [
        (button.text, button.callback_data)
        for row in keyboards.build_history_section_keyboard().keyboard
        for button in row
    ]

    assert buttons == [
        ("📅 На дату", "history_section:daily"),
        ("📊 Средние климатические показатели", "history_section:climate"),
        ("⬅️ В меню", "history_menu"),
    ]


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
        ("Ввести дату", "history_date_custom"),
        ("⬅️ В меню", "history_menu"),
    ]


def test_history_climate_mode_keyboard_contains_branching_actions(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    buttons = [
        (button.text, button.callback_data)
        for row in keyboards.build_history_climate_mode_keyboard().keyboard
        for button in row
    ]

    assert buttons == [
        ("🗓 Месяц конкретного года", "history_climate_mode:monthly_year"),
        ("📆 Среднемесячные показатели", "history_climate_mode:monthly_normals"),
        ("⬅️ Назад", "history_climate_back_to_actions"),
        ("⬅️ В меню", "history_menu"),
    ]


def test_history_month_keyboard_contains_all_months(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    texts = _button_texts(keyboards.build_history_month_keyboard())

    assert texts[:12] == [
        "Январь",
        "Февраль",
        "Март",
        "Апрель",
        "Май",
        "Июнь",
        "Июль",
        "Август",
        "Сентябрь",
        "Октябрь",
        "Ноябрь",
        "Декабрь",
    ]
    assert texts[-2:] == ["⬅️ Назад", "⬅️ В меню"]


def test_history_year_clarification_keyboard_contains_past_options_and_retry(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)

    buttons = [
        (button.text, button.callback_data)
        for row in keyboards.build_history_year_clarification_keyboard([date(2025, 6, 8), date(1925, 6, 8)]).keyboard
        for button in row
    ]

    assert buttons == [
        ("08.06.2025", "history_date_year:2025-06-08"),
        ("08.06.1925", "history_date_year:1925-06-08"),
        ("Ввести другую дату", "history_date_custom"),
    ]


# ---------------------------------------------------------------------------
# Telegram callback_data byte-length safety net
# Telegram enforces a hard limit of 64 bytes per callback_data value.
# The tests below verify that every inline keyboard factory function in
# keyboards.py produces callback_data strings within that limit.
# Dynamic keyboards are exercised with realistic sample inputs:
#   - date strings in DD.MM.YYYY format (10 chars)
#   - UUID-style location IDs (36 chars – the longest realistic value)
# ---------------------------------------------------------------------------

_TELEGRAM_CALLBACK_LIMIT = 64


def _all_callback_data(markup) -> list[str]:
    """Return all callback_data strings from an inline keyboard markup."""
    result = []
    for row in getattr(markup, "keyboard", []):
        for button in row:
            cd = getattr(button, "callback_data", None)
            if cd is not None:
                result.append(cd)
    return result


def _assert_within_limit(callback_data_list: list[str], source: str) -> None:
    for cd in callback_data_list:
        byte_len = len(cd.encode("utf-8"))
        assert byte_len <= _TELEGRAM_CALLBACK_LIMIT, (
            f"callback_data from {source!r} exceeds {_TELEGRAM_CALLBACK_LIMIT} bytes "
            f"({byte_len} bytes): {cd!r}"
        )


def test_yes_no_menu_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    cds = _all_callback_data(keyboards.yes_no_menu())
    assert cds, "yes_no_menu should have inline buttons"
    _assert_within_limit(cds, "yes_no_menu")


def test_history_section_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    cds = _all_callback_data(keyboards.build_history_section_keyboard())
    _assert_within_limit(cds, "build_history_section_keyboard")


def test_history_date_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    cds = _all_callback_data(keyboards.build_history_date_keyboard())
    _assert_within_limit(cds, "build_history_date_keyboard")


def test_history_climate_mode_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    cds = _all_callback_data(keyboards.build_history_climate_mode_keyboard())
    _assert_within_limit(cds, "build_history_climate_mode_keyboard")


def test_history_month_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    cds = _all_callback_data(keyboards.build_history_month_keyboard())
    assert len(cds) >= 12, "All 12 months must be represented"
    _assert_within_limit(cds, "build_history_month_keyboard")


def test_history_year_clarification_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    options = [date(2025, 6, 8), date(2024, 6, 8), date(1990, 6, 8)]
    cds = _all_callback_data(keyboards.build_history_year_clarification_keyboard(options))
    _assert_within_limit(cds, "build_history_year_clarification_keyboard")


def test_ai_compare_date_post_result_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    cds = _all_callback_data(keyboards.build_ai_compare_date_post_result_keyboard())
    _assert_within_limit(cds, "build_ai_compare_date_post_result_keyboard")


def test_source_compare_date_post_result_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    cds = _all_callback_data(keyboards.build_source_compare_date_post_result_keyboard())
    _assert_within_limit(cds, "build_source_compare_date_post_result_keyboard")


def test_forecast_days_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    days = ["08.06.2025", "09.06.2025", "10.06.2025", "11.06.2025", "12.06.2025"]
    cds = _all_callback_data(keyboards.build_forecast_days_keyboard(days))
    _assert_within_limit(cds, "build_forecast_days_keyboard")


def test_forecast_day_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    days = ["08.06.2025", "09.06.2025", "10.06.2025"]
    cds = _all_callback_data(keyboards.build_forecast_day_keyboard(days, "09.06.2025"))
    _assert_within_limit(cds, "build_forecast_day_keyboard")


def test_ai_compare_days_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    days = ["08.06.2025", "09.06.2025", "10.06.2025", "11.06.2025", "12.06.2025"]
    cds = _all_callback_data(keyboards.build_ai_compare_days_keyboard(days))
    _assert_within_limit(cds, "build_ai_compare_days_keyboard")


def test_source_compare_days_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    days = ["08.06.2025", "09.06.2025", "10.06.2025", "11.06.2025", "12.06.2025"]
    cds = _all_callback_data(keyboards.build_source_compare_days_keyboard(days))
    _assert_within_limit(cds, "build_source_compare_days_keyboard")


def test_saved_locations_keyboard_callback_data_within_limit(monkeypatch):
    """UUID-style location_id (36 chars) is the longest realistic value."""
    keyboards = _load_keyboards(monkeypatch)
    sample_uuid = "550e8400-e29b-41d4-a716-446655440000"  # 36 chars
    saved_locations = [
        {"id": sample_uuid, "title": "Дом", "label": "Москва, RU"},
        {"id": "abc123", "title": "Работа", "label": "Берлин, DE"},
    ]
    for prefix in [
        "favorite_pick",
        "current_saved_pick",
        "details_saved_pick",
        "forecast_saved_pick",
        "source_compare_saved_pick",
        "history_saved_pick",
        "aicmp_saved_pick:1",
        "aicmp_saved_pick:2",
        "delete_location_pick",
        "rename_location_pick",
    ]:
        cds = _all_callback_data(keyboards.build_saved_locations_keyboard(saved_locations, prefix))
        _assert_within_limit(cds, f"build_saved_locations_keyboard(prefix={prefix!r})")


def test_alert_subscriptions_keyboard_callback_data_within_limit(monkeypatch):
    keyboards = _load_keyboards(monkeypatch)
    sample_uuid = "550e8400-e29b-41d4-a716-446655440000"
    subscriptions = [
        {"location_id": sample_uuid, "title": "Дом", "label": "Москва, RU"},
        {"location_id": "shortid", "title": "Работа", "label": "Berlin, DE"},
    ]
    for prefix in [
        "alerts_sub_toggle",
        "alerts_sub_interval",
        "alerts_sub_delete",
        "alerts_sub_add_saved",
    ]:
        cds = _all_callback_data(
            keyboards.build_alert_subscriptions_keyboard(subscriptions, prefix)
        )
        _assert_within_limit(cds, f"build_alert_subscriptions_keyboard(prefix={prefix!r})")


def test_location_pick_keyboard_callback_data_within_limit(monkeypatch):
    """build_location_pick_keyboard uses indices (0-based) — always short."""
    keyboards = _load_keyboards(monkeypatch)
    monkeypatch.setattr(
        keyboards,
        "build_disambiguated_location_labels",
        lambda locs: [f"Город {i}" for i in range(len(locs))],
    )
    locations = [{"name": f"City{i}", "country": "RU", "lat": 55.0 + i, "lon": 37.0} for i in range(10)]
    for scenario, extra in [
        ("current_pick", {"cancel": "current_cancel"}),
        ("details_pick", {"cancel": "details_cancel"}),
        ("forecast_pick", {"cancel": "forecast_cancel"}),
        ("history_pick", {"cancel": "history_cancel"}),
        ("source_compare_pick", {"cancel": "source_compare_cancel"}),
        ("compare_pick", {"cancel": "compare_cancel", "step": 1}),
        ("compare_pick", {"cancel": "compare_cancel", "step": 2}),
    ]:
        step = extra.get("step")
        cds = _all_callback_data(
            keyboards.build_location_pick_keyboard(
                locations,
                scenario,
                extra["cancel"],
                compare_step=step,
            )
        )
        _assert_within_limit(cds, f"build_location_pick_keyboard(prefix={scenario!r}, step={step})")
