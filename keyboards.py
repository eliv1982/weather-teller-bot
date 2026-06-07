from datetime import date

from telebot import types

from weather.locations import build_disambiguated_location_labels
from callbacks.constants import (
    # yes/no
    YN_YES, YN_NO, YN_MENU,
    # current weather
    CURRENT_CANCEL,
    # forecast
    FORECAST_DAY_PREFIX, FORECAST_BACK, FORECAST_MENU,
    AI_FORECAST_DAY_PREFIX,
    # ai compare
    AICMP_SAVED_PICK_PREFIX, AICMP_SAVED_CANCEL,
    AICMP_DATE_PICK_PREFIX, AICMP_DATE_CANCEL, AICMP_DATE_ANOTHER,
    # source compare
    SOURCE_COMPARE_DATE_PICK_PREFIX, SOURCE_COMPARE_DATE_CANCEL,
    SOURCE_COMPARE_DATE_ANOTHER,
    # history
    HISTORY_SECTION_PREFIX, HISTORY_SECTION_DAILY, HISTORY_SECTION_CLIMATE,
    HISTORY_MENU,
    HISTORY_DATE_PRESET_PREFIX,
    HISTORY_PRESET_YESTERDAY, HISTORY_PRESET_7D, HISTORY_PRESET_30D,
    HISTORY_DATE_CUSTOM,
    HISTORY_CLIMATE_MODE_PREFIX,
    HISTORY_CLIMATE_MODE_MONTHLY_YEAR, HISTORY_CLIMATE_MODE_MONTHLY_NORMALS,
    HISTORY_CLIMATE_BACK_TO_ACTIONS, HISTORY_CLIMATE_BACK_TO_MODES,
    HISTORY_CLIMATE_MONTH_PREFIX,
    HISTORY_DATE_YEAR_PREFIX,
    # saved locations / favorite
    FAVORITE_PICK_PREFIX,
    # scenario routing cancel callbacks
    DETAILS_CANCEL, FORECAST_CANCEL, SOURCE_COMPARE_CANCEL,
    HISTORY_CANCEL, COMPARE_CANCEL,
)


def _persistent_reply_keyboard() -> types.ReplyKeyboardMarkup:
    """Создаёт reply-клавиатуру, которая не скрывается после одного нажатия."""
    return types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def main_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт главное меню бота."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("🌦 Прогноз погоды"), types.KeyboardButton("📍 Локации"))
    keyboard.row(types.KeyboardButton("🔔 Подписки"), types.KeyboardButton("ℹ️ Помощь"))
    return keyboard


def weather_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт меню погодных сценариев."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("🌡 Погода сейчас"), types.KeyboardButton("☀️ Прогноз на сегодня"))
    keyboard.row(types.KeyboardButton("🌤 Прогноз на завтра"), types.KeyboardButton("📅 Прогноз на 5 дней"))
    keyboard.row(types.KeyboardButton("🧭 Расширенные данные"), types.KeyboardButton("📅 История погоды"))
    keyboard.row(types.KeyboardButton("🔎 Сравнить источники"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def source_compare_mode_menu() -> types.ReplyKeyboardMarkup:
    """Подменю выбора режима сравнения OpenWeather и Open-Meteo."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("🌡 Сейчас"), types.KeyboardButton("☀️ Сегодня"))
    keyboard.row(types.KeyboardButton("🌤 Завтра"), types.KeyboardButton("📅 На дату"))
    keyboard.row(types.KeyboardButton("⬅️ Назад"))
    return keyboard


def geo_request_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт клавиатуру для запроса геолокации."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("Отправить геолокацию", request_location=True))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def yes_no_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт inline-клавиатуру выбора Да/Нет."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Да", callback_data=YN_YES),
        types.InlineKeyboardButton("Нет", callback_data=YN_NO),
    )
    keyboard.add(types.InlineKeyboardButton("⬅️ В меню", callback_data=YN_MENU))
    return keyboard


def alerts_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт меню раздела уведомлений."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("📋 Показать подписки"), types.KeyboardButton("➕ Добавить локацию в уведомления"))
    keyboard.row(
        types.KeyboardButton("🔔 Включить/выключить подписку"),
        types.KeyboardButton("⏱ Изменить интервал подписки"),
    )
    keyboard.row(types.KeyboardButton("🗑 Удалить подписку"), types.KeyboardButton("⬅️ В меню"))
    return keyboard


def alerts_add_location_menu(*, has_saved_locations: bool = True) -> types.ReplyKeyboardMarkup:
    """Подменю выбора способа добавления локации в подписки уведомлений."""
    keyboard = _persistent_reply_keyboard()
    if has_saved_locations:
        keyboard.row(types.KeyboardButton("⭐ Из сохранённых"))
    keyboard.row(
        types.KeyboardButton("🧭 Координаты"),
        types.KeyboardButton("📍 Геолокация", request_location=True),
    )
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def location_input_menu(*, has_saved_locations: bool = False) -> types.ReplyKeyboardMarkup:
    """Подменю выбора способа ввода локации для погодных сценариев."""
    keyboard = _persistent_reply_keyboard()
    if has_saved_locations:
        keyboard.row(types.KeyboardButton("⭐ Из сохранённых"))
    keyboard.row(
        types.KeyboardButton("🧭 Координаты"),
        types.KeyboardButton("📍 Отправить геолокацию", request_location=True),
    )
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def alerts_first_enable_location_menu() -> types.ReplyKeyboardMarkup:
    """Подменю выбора локации для первого включения уведомлений."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("Использовать текущую локацию"))
    keyboard.row(types.KeyboardButton("Выбрать из сохранённых"))
    keyboard.row(types.KeyboardButton("Ввести населённый пункт"))
    keyboard.row(types.KeyboardButton("Отправить геолокацию"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def build_alert_subscriptions_keyboard(subscriptions: list[dict], callback_prefix: str) -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру выбора подписки уведомлений."""
    keyboard = types.InlineKeyboardMarkup()
    for item in subscriptions:
        if not isinstance(item, dict):
            continue
        location_id = item.get("location_id")
        if not isinstance(location_id, str) or not location_id:
            continue
        title = str(item.get("title") or item.get("label") or "Локация").strip()
        label = str(item.get("label") or "").strip()
        button_text = f"{title} — {label}" if label else title
        if len(button_text) > 64:
            button_text = button_text[:61] + "..."
        keyboard.add(
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"{callback_prefix}:{location_id}",
            )
        )
    return keyboard


def locations_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт меню управления сохранёнными локациями."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("📋 Показать мои локации"), types.KeyboardButton("⚖️ Сравнить локации"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def saved_locations_management_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт меню действий со списком сохранённых локаций."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("➕ Добавить локацию"), types.KeyboardButton("🗑 Удалить локацию"))
    keyboard.row(types.KeyboardButton("✏️ Изменить локацию"), types.KeyboardButton("⚖️ Сравнить локации"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def add_saved_location_menu() -> types.ReplyKeyboardMarkup:
    """Подменю выбора способа добавления новой локации."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(
        types.KeyboardButton("🧭 Координаты"),
        types.KeyboardButton("📍 Отправить геолокацию", request_location=True),
    )
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def add_saved_location_unresolved_coords_menu() -> types.ReplyKeyboardMarkup:
    """Подменю для случая, когда по координатам не найден населённый пункт."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("💾 Сохранить как точку"))
    keyboard.row(
        types.KeyboardButton("🧭 Ввести координаты заново"),
        types.KeyboardButton("🏙 Ввести населённый пункт"),
    )
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def build_forecast_days_keyboard(days: list[str]) -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру с днями прогноза."""
    keyboard = types.InlineKeyboardMarkup()
    for day in days:
        keyboard.add(types.InlineKeyboardButton(text=day, callback_data=f"{FORECAST_DAY_PREFIX}:{day}"))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ В меню", callback_data=FORECAST_MENU))
    return keyboard


def build_forecast_day_keyboard(days: list[str], current_day: str) -> types.InlineKeyboardMarkup:
    """Создаёт inline-кнопки для выбранного дня прогноза."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="📅 К дням", callback_data=FORECAST_BACK))
    keyboard.add(
        types.InlineKeyboardButton(
            text="🪄 Краткая рекомендация",
            callback_data=f"{AI_FORECAST_DAY_PREFIX}:{current_day}",
        )
    )

    index = days.index(current_day)
    nav_buttons = []
    if index > 0:
        prev_day = days[index - 1]
        nav_buttons.append(types.InlineKeyboardButton(text="◀️", callback_data=f"{FORECAST_DAY_PREFIX}:{prev_day}"))
    if index < len(days) - 1:
        next_day = days[index + 1]
        nav_buttons.append(types.InlineKeyboardButton(text="▶️", callback_data=f"{FORECAST_DAY_PREFIX}:{next_day}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    keyboard.add(types.InlineKeyboardButton(text="⬅️ В меню", callback_data=FORECAST_MENU))

    return keyboard


def build_ai_action_keyboard(button_text: str, callback_data: str) -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру с одной AI-кнопкой действия."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=callback_data))
    return keyboard


def ai_compare_mode_menu() -> types.ReplyKeyboardMarkup:
    """Подменю выбора режима умного AI-сравнения локаций."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("⚖️ Сравнить сейчас"), types.KeyboardButton("📅 Сравнить на дату"))
    keyboard.row(types.KeyboardButton("⬅️ Назад"))
    return keyboard


def ai_compare_location_method_menu() -> types.ReplyKeyboardMarkup:
    """Подменю выбора способа задания локации для AI-сравнения."""
    keyboard = _persistent_reply_keyboard()
    keyboard.row(types.KeyboardButton("⭐ Из сохранённых"))
    keyboard.row(
        types.KeyboardButton("🧭 Координаты"),
        types.KeyboardButton("📍 Геолокация", request_location=True),
    )
    keyboard.row(types.KeyboardButton("⬅️ Отмена"))
    return keyboard


def build_ai_compare_saved_locations_keyboard(saved_locations: list[dict], step: int) -> types.InlineKeyboardMarkup:
    """Создаёт inline-выбор сохранённой локации для шага AI-сравнения."""
    keyboard = build_saved_locations_keyboard(saved_locations, f"{AICMP_SAVED_PICK_PREFIX}:{step}")
    keyboard.add(types.InlineKeyboardButton(text="⬅️ Отмена", callback_data=AICMP_SAVED_CANCEL))
    return keyboard


def build_ai_compare_days_keyboard(days: list[str]) -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру выбора даты для AI-сравнения локаций."""
    keyboard = types.InlineKeyboardMarkup()
    for day in days:
        keyboard.add(types.InlineKeyboardButton(text=day, callback_data=f"{AICMP_DATE_PICK_PREFIX}:{day}"))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ Отмена", callback_data=AICMP_DATE_CANCEL))
    return keyboard


def build_ai_compare_date_post_result_keyboard() -> types.InlineKeyboardMarkup:
    """Действия после результата AI-сравнения на дату (ещё одна дата или выход в меню)."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton(text="📅 Выбрать другую дату", callback_data=AICMP_DATE_ANOTHER),
        types.InlineKeyboardButton(text="⬅️ В меню", callback_data=YN_MENU),
    )
    return keyboard


def build_source_compare_days_keyboard(days: list[str]) -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру выбора даты для сравнения источников."""
    keyboard = types.InlineKeyboardMarkup()
    for day in days:
        keyboard.add(types.InlineKeyboardButton(text=day, callback_data=f"{SOURCE_COMPARE_DATE_PICK_PREFIX}:{day}"))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ Отмена", callback_data=SOURCE_COMPARE_DATE_CANCEL))
    return keyboard


def build_source_compare_date_post_result_keyboard() -> types.InlineKeyboardMarkup:
    """Действия после сравнения источников на выбранную дату."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton(text="📅 Выбрать другую дату", callback_data=SOURCE_COMPARE_DATE_ANOTHER),
        types.InlineKeyboardButton(text="⬅️ В меню", callback_data=YN_MENU),
    )
    return keyboard


def build_history_section_keyboard() -> types.InlineKeyboardMarkup:
    """Создает первое inline-подменю для раздела архивной погоды."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(
        text="📅 На дату",
        callback_data=f"{HISTORY_SECTION_PREFIX}:{HISTORY_SECTION_DAILY}",
    ))
    keyboard.add(types.InlineKeyboardButton(
        text="📊 Средние климатические показатели",
        callback_data=f"{HISTORY_SECTION_PREFIX}:{HISTORY_SECTION_CLIMATE}",
    ))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ В меню", callback_data=HISTORY_MENU))
    return keyboard


def build_history_date_keyboard() -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру выбора даты для архивной погоды."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(
        text="Вчера",
        callback_data=f"{HISTORY_DATE_PRESET_PREFIX}:{HISTORY_PRESET_YESTERDAY}",
    ))
    keyboard.add(types.InlineKeyboardButton(
        text="7 дней назад",
        callback_data=f"{HISTORY_DATE_PRESET_PREFIX}:{HISTORY_PRESET_7D}",
    ))
    keyboard.add(types.InlineKeyboardButton(
        text="30 дней назад",
        callback_data=f"{HISTORY_DATE_PRESET_PREFIX}:{HISTORY_PRESET_30D}",
    ))
    keyboard.add(types.InlineKeyboardButton(text="Ввести дату", callback_data=HISTORY_DATE_CUSTOM))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ В меню", callback_data=HISTORY_MENU))
    return keyboard


def build_history_climate_mode_keyboard() -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру выбора режима климатической справки."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(
        text="🗓 Месяц конкретного года",
        callback_data=f"{HISTORY_CLIMATE_MODE_PREFIX}:{HISTORY_CLIMATE_MODE_MONTHLY_YEAR}",
    ))
    keyboard.add(types.InlineKeyboardButton(
        text="📆 Среднемесячные показатели",
        callback_data=f"{HISTORY_CLIMATE_MODE_PREFIX}:{HISTORY_CLIMATE_MODE_MONTHLY_NORMALS}",
    ))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=HISTORY_CLIMATE_BACK_TO_ACTIONS))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ В меню", callback_data=HISTORY_MENU))
    return keyboard


def build_history_month_keyboard() -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру выбора месяца для климатической справки."""
    keyboard = types.InlineKeyboardMarkup()
    month_labels = [
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
    for row_start in range(0, len(month_labels), 3):
        row_buttons = []
        for index, label in enumerate(month_labels[row_start : row_start + 3], start=row_start + 1):
            row_buttons.append(types.InlineKeyboardButton(
                text=label,
                callback_data=f"{HISTORY_CLIMATE_MONTH_PREFIX}:{index}",
            ))
        keyboard.row(*row_buttons)
    keyboard.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=HISTORY_CLIMATE_BACK_TO_MODES))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ В меню", callback_data=HISTORY_MENU))
    return keyboard


def build_history_year_clarification_keyboard(options: list[date]) -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру для уточнения полного года в короткой дате."""
    keyboard = types.InlineKeyboardMarkup()
    for option in options:
        keyboard.add(types.InlineKeyboardButton(
            text=option.strftime("%d.%m.%Y"),
            callback_data=f"{HISTORY_DATE_YEAR_PREFIX}:{option.isoformat()}",
        ))
    keyboard.add(types.InlineKeyboardButton(text="Ввести другую дату", callback_data=HISTORY_DATE_CUSTOM))
    return keyboard


def build_location_pick_keyboard(
    locations: list[dict],
    pick_callback_prefix: str,
    cancel_callback_data: str,
    *,
    compare_step: int | None = None,
) -> types.InlineKeyboardMarkup:
    """
    Универсальная inline-клавиатура выбора населённого пункта из списка геокодинга.

    Подписи на кнопках строятся через build_disambiguated_location_labels: при одинаковых
    названиях к дублям добавляются координаты.

    pick_callback_prefix — префикс callback_data, например «details_pick» или «compare_pick».
    cancel_callback_data — полное значение callback для кнопки «Отмена».
    compare_step — для сравнения: шаг 1 или 2, тогда callback_data вида «compare_pick:1:0».
    """
    keyboard = types.InlineKeyboardMarkup()
    labels = build_disambiguated_location_labels(locations)
    for index, _ in enumerate(locations):
        label = labels[index]
        if len(label) > 64:
            label = label[:61] + "..."
        if compare_step is not None:
            callback_data = f"{pick_callback_prefix}:{compare_step}:{index}"
        else:
            callback_data = f"{pick_callback_prefix}:{index}"
        keyboard.add(
            types.InlineKeyboardButton(
                text=label,
                callback_data=callback_data,
            )
        )
    keyboard.add(types.InlineKeyboardButton(text="⬅️ Отмена", callback_data=cancel_callback_data))
    return keyboard


def build_scenario_location_choice_keyboard(
    locations: list[dict],
    scenario: str,
    *,
    compare_step: int | None = None,
) -> types.InlineKeyboardMarkup:
    """
    Inline-клавиатура выбора локации для сценария details / forecast / history / compare.

    scenario: «details», «forecast», «history» или «compare»; для compare обязательно передай compare_step (1 или 2).
    """
    if scenario == "details":
        return build_location_pick_keyboard(locations, "details_pick", DETAILS_CANCEL)
    if scenario == "forecast":
        return build_location_pick_keyboard(locations, "forecast_pick", FORECAST_CANCEL)
    if scenario == "source_compare":
        return build_location_pick_keyboard(locations, "source_compare_pick", SOURCE_COMPARE_CANCEL)
    if scenario == "history":
        return build_location_pick_keyboard(locations, "history_pick", HISTORY_CANCEL)
    if scenario == "compare":
        if compare_step not in (1, 2):
            raise ValueError("Для сценария compare нужен compare_step равный 1 или 2.")
        return build_location_pick_keyboard(
            locations,
            "compare_pick",
            COMPARE_CANCEL,
            compare_step=compare_step,
        )
    raise ValueError(f"Неизвестный сценарий: {scenario}")


def build_current_weather_location_keyboard(locations: list[dict]) -> types.InlineKeyboardMarkup:
    """Inline-клавиатура выбора для сценария «Текущая погода»."""
    return build_location_pick_keyboard(locations, "current_pick", CURRENT_CANCEL)


def build_saved_locations_keyboard(
    saved_locations: list[dict],
    callback_prefix: str,
) -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру выбора сохранённой локации по заданному префиксу callback."""
    keyboard = types.InlineKeyboardMarkup()
    for item in saved_locations:
        if not isinstance(item, dict):
            continue
        location_id = item.get("id")
        if not isinstance(location_id, str) or not location_id:
            continue
        title = (item.get("title") or "Без названия").strip()
        label = (item.get("label") or "").strip()
        button_text = f"{title} — {label}" if label else title
        if len(button_text) > 64:
            button_text = button_text[:61] + "..."
        keyboard.add(
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"{callback_prefix}:{location_id}",
            )
        )
    return keyboard


def build_favorite_pick_keyboard(saved_locations: list[dict]) -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру выбора основной локации."""
    return build_saved_locations_keyboard(saved_locations, FAVORITE_PICK_PREFIX)
