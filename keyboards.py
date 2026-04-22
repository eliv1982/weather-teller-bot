from telebot import types

from weather_app import build_disambiguated_location_labels


def main_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт главное меню бота."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Текущая погода"), types.KeyboardButton("Прогноз на 5 дней"))
    keyboard.row(types.KeyboardButton("Моя геолокация"), types.KeyboardButton("Сравнить города"))
    keyboard.row(types.KeyboardButton("Расширенные данные"), types.KeyboardButton("Мои локации"))
    keyboard.row(types.KeyboardButton("Уведомления"))
    keyboard.row(types.KeyboardButton("Помощь"))
    return keyboard


def geo_request_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт клавиатуру для запроса геолокации."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Отправить геолокацию", request_location=True))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def alerts_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт меню раздела уведомлений."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Показать подписки"))
    keyboard.row(types.KeyboardButton("Добавить локацию в уведомления"))
    keyboard.row(types.KeyboardButton("Включить/выключить подписку"))
    keyboard.row(types.KeyboardButton("Изменить интервал подписки"))
    keyboard.row(types.KeyboardButton("Удалить подписку"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def alerts_add_location_menu() -> types.ReplyKeyboardMarkup:
    """Подменю выбора способа добавления локации в подписки уведомлений."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Выбрать из сохранённых"))
    keyboard.row(types.KeyboardButton("Ввести населённый пункт"))
    keyboard.row(types.KeyboardButton("Отправить геолокацию"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def alerts_first_enable_location_menu() -> types.ReplyKeyboardMarkup:
    """Подменю выбора локации для первого включения уведомлений."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
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
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Сохранить текущую локацию"))
    keyboard.row(types.KeyboardButton("Добавить новую локацию"))
    keyboard.row(types.KeyboardButton("Показать мои локации"))
    keyboard.row(types.KeyboardButton("Сделать основной"))
    keyboard.row(types.KeyboardButton("Переименовать локацию"), types.KeyboardButton("Удалить локацию"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def add_saved_location_menu() -> types.ReplyKeyboardMarkup:
    """Подменю выбора способа добавления новой локации."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Ввести населённый пункт"))
    keyboard.row(types.KeyboardButton("Отправить геолокацию"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def build_forecast_days_keyboard(days: list[str]) -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру с днями прогноза."""
    keyboard = types.InlineKeyboardMarkup()
    for day in days:
        keyboard.add(types.InlineKeyboardButton(text=day, callback_data=f"forecast_day:{day}"))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ В меню", callback_data="forecast_menu"))
    return keyboard


def build_forecast_day_keyboard(days: list[str], current_day: str) -> types.InlineKeyboardMarkup:
    """Создаёт inline-кнопки для выбранного дня прогноза."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="📅 К дням", callback_data="forecast_back"))

    index = days.index(current_day)
    nav_buttons = []
    if index > 0:
        prev_day = days[index - 1]
        nav_buttons.append(types.InlineKeyboardButton(text="◀️", callback_data=f"forecast_day:{prev_day}"))
    if index < len(days) - 1:
        next_day = days[index + 1]
        nav_buttons.append(types.InlineKeyboardButton(text="▶️", callback_data=f"forecast_day:{next_day}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    keyboard.add(types.InlineKeyboardButton(text="⬅️ В меню", callback_data="forecast_menu"))

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
    Inline-клавиатура выбора локации для сценария details / forecast / compare.

    scenario: «details», «forecast» или «compare»; для compare обязательно передай compare_step (1 или 2).
    """
    if scenario == "details":
        return build_location_pick_keyboard(locations, "details_pick", "details_cancel")
    if scenario == "forecast":
        return build_location_pick_keyboard(locations, "forecast_pick", "forecast_cancel")
    if scenario == "compare":
        if compare_step not in (1, 2):
            raise ValueError("Для сценария compare нужен compare_step равный 1 или 2.")
        return build_location_pick_keyboard(
            locations,
            "compare_pick",
            "compare_cancel",
            compare_step=compare_step,
        )
    raise ValueError(f"Неизвестный сценарий: {scenario}")


def build_current_weather_location_keyboard(locations: list[dict]) -> types.InlineKeyboardMarkup:
    """Inline-клавиатура выбора для сценария «Текущая погода»."""
    return build_location_pick_keyboard(locations, "current_pick", "current_cancel")


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
    return build_saved_locations_keyboard(saved_locations, "favorite_pick")
