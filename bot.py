import os
import logging
import time
import threading
from datetime import datetime
from dotenv import load_dotenv
import telebot
from telebot import types
from weather_app import (
    get_coordinates,
    get_locations,
    get_current_weather,
    get_forecast_5d3h,
    get_air_pollution,
    analyze_air_pollution,
    build_disambiguated_location_labels,
    build_geocode_item_with_disambiguated_label,
    build_location_label,
    get_location_by_coordinates,
)
from storage import load_user, save_user, load_all_users, save_all_users


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("Ошибка: BOT_TOKEN не найден. Проверь файл .env.")
    logger.error("Ошибка запуска: BOT_TOKEN не найден в файле .env.")
    raise SystemExit(0)


bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}
compare_drafts = {}
details_saved_drafts = {}
forecast_saved_drafts = {}
forecast_cache = {}
# Варианты локаций для сценария «Текущая погода» (несколько совпадений геокодинга)
current_location_choices = {}
# Варианты локаций при смене локации для уведомлений (несколько совпадений геокодинга)
alerts_location_choices = {}

MENU_BUTTONS = [
    "Текущая погода",
    "Прогноз на 5 дней",
    "Моя геолокация",
    "Сравнить города",
    "Расширенные данные",
    "Уведомления",
    "Помощь",
]


def wind_direction_ru(deg: float) -> str:
    """Переводит градусы направления ветра в русское направление."""
    directions = [
        "северный",
        "северо-восточный",
        "восточный",
        "юго-восточный",
        "южный",
        "юго-западный",
        "западный",
        "северо-западный",
    ]
    index = round(deg / 45) % 8
    return directions[index]


def help_text() -> str:
    """Возвращает текст справки по командам бота."""
    return (
        "ℹ️ Доступные команды:\n"
        "/start — главное меню\n"
        "/current — текущая погода\n"
        "/forecast — прогноз на 5 дней\n"
        "/geo — погода по геолокации\n"
        "/compare — сравнить города\n"
        "/details — расширенные данные\n"
        "/alerts — уведомления"
    )


def alerts_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт меню раздела уведомлений."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Включить уведомления"), types.KeyboardButton("Выключить уведомления"))
    keyboard.row(types.KeyboardButton("Изменить интервал"), types.KeyboardButton("Показать статус"))
    keyboard.row(types.KeyboardButton("Изменить локацию"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def alerts_location_menu() -> types.ReplyKeyboardMarkup:
    """Подменю выбора способа указания локации для уведомлений."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Ввести населённый пункт"))
    keyboard.row(types.KeyboardButton("Отправить геолокацию"))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


def format_alerts_status(user_data: dict) -> str:
    """Форматирует статус уведомлений пользователя."""
    city = user_data.get("city") or "Не выбрана"
    notifications = user_data.get("notifications", {}) if isinstance(user_data.get("notifications"), dict) else {}
    enabled = notifications.get("enabled", False)
    interval_h = notifications.get("interval_h", 2)
    if not isinstance(interval_h, int) or interval_h <= 0:
        interval_h = 2

    return (
        "🔔 Статус уведомлений:\n"
        f"• 📍 Локация: {city}\n"
        f"• 🔔 Уведомления: {'включены' if enabled else 'выключены'}\n"
        f"• 🕒 Интервал проверки: {interval_h} ч"
    )


def detect_weather_alerts(forecast_items: list[dict]) -> list[str]:
    """Ищет в прогнозе ближайшие заметные ухудшения погоды."""
    keywords = ("дожд", "ливень", "гроза", "снег", "метель", "туман")
    alerts: list[str] = []

    for item in forecast_items[:8]:
        description = item.get("weather", [{}])[0].get("description", "")
        lowered = description.lower()
        if any(keyword in lowered for keyword in keywords):
            dt_txt = item.get("dt_txt", "")
            if " " in dt_txt:
                date_part, time_part = dt_txt.split(" ", 1)
                try:
                    date_fmt = datetime.strptime(date_part, "%Y-%m-%d").strftime("%d.%m")
                except ValueError:
                    date_fmt = date_part
                short = f"{date_fmt} {time_part[:5]} — {description}"
            else:
                short = f"{dt_txt} — {description}"
            alerts.append(short)

    return alerts


def ensure_notifications_defaults(user_data: dict) -> dict:
    """Гарантирует корректную структуру notifications в данных пользователя."""
    notifications = user_data.get("notifications", {})
    if not isinstance(notifications, dict):
        notifications = {}

    interval_h = notifications.get("interval_h", 2)
    if not isinstance(interval_h, int) or interval_h <= 0:
        interval_h = 2

    last_check_ts = notifications.get("last_check_ts", 0)
    if not isinstance(last_check_ts, (int, float)):
        last_check_ts = 0

    notifications["enabled"] = bool(notifications.get("enabled", False))
    notifications["interval_h"] = interval_h
    notifications["last_check_ts"] = int(last_check_ts)
    user_data["notifications"] = notifications
    return user_data


def start_alerts_flow(message: types.Message) -> None:
    """Запускает раздел уведомлений."""
    user_id = message.from_user.id
    logger.info("Пользователь %s вошёл в раздел уведомлений.", user_id)
    user_data = load_user(user_id)
    lat = user_data.get("lat")
    lon = user_data.get("lon")

    if lat is None or lon is None:
        bot.send_message(
            message.chat.id,
            "Сначала нужно сохранить локацию. Используй «Текущая погода» или «Моя геолокация».",
            reply_markup=main_menu(),
        )
        return

    user_states[user_id] = "alerts_menu"
    bot.send_message(message.chat.id, format_alerts_status(user_data), reply_markup=alerts_menu())


def alerts_worker() -> None:
    """Фоновая проверка прогноза для уведомлений."""
    logger.info("Фоновый поток уведомлений запущен.")

    while True:
        try:
            all_users = load_all_users()
            changed = False
            now_ts = int(time.time())

            for user_id_str, user_data in all_users.items():
                if not isinstance(user_data, dict):
                    continue

                user_data = ensure_notifications_defaults(user_data)
                notifications = user_data["notifications"]

                if not notifications.get("enabled", False):
                    continue

                lat = user_data.get("lat")
                lon = user_data.get("lon")
                if lat is None or lon is None:
                    continue

                interval_h = notifications.get("interval_h", 2)
                last_check_ts = notifications.get("last_check_ts", 0)
                if now_ts - int(last_check_ts) < interval_h * 3600:
                    continue

                forecast_items = get_forecast_5d3h(lat, lon)
                if not forecast_items:
                    logger.warning("Не удалось получить прогноз в фоновом потоке для пользователя %s.", user_id_str)
                    notifications["last_check_ts"] = now_ts
                    changed = True
                    continue

                alerts = detect_weather_alerts(forecast_items)
                if alerts:
                    city = user_data.get("city") or "неизвестная локация"
                    alert_text = (
                        "🌤 Weather Teller\n"
                        f"Для локации {city} найдено изменение погоды:\n"
                        f"• {alerts[0]}\n"
                        "Проверь прогноз в боте."
                    )
                    try:
                        bot.send_message(int(user_id_str), alert_text)
                        logger.info("Уведомление успешно отправлено пользователю %s.", user_id_str)
                    except Exception:
                        logger.warning("Не удалось отправить уведомление пользователю %s.", user_id_str)

                notifications["last_check_ts"] = now_ts
                changed = True

            if changed:
                save_all_users(all_users)
        except Exception:
            logger.exception("Ошибка в фоновом потоке уведомлений.")

        time.sleep(60)


def start_current_weather_flow(message: types.Message) -> None:
    """Запускает сценарий ввода населённого пункта для текущей погоды."""
    user_id = message.from_user.id
    current_location_choices.pop(user_id, None)
    user_states[user_id] = "waiting_current_weather_city"
    bot.send_message(message.chat.id, "Введи название населённого пункта.")


def start_geo_weather_flow(message: types.Message) -> None:
    """Запускает сценарий получения погоды по геолокации."""
    logger.info("Запущен сценарий геолокации для пользователя %s.", message.from_user.id)
    user_states[message.from_user.id] = "waiting_geo_location"
    bot.send_message(
        message.chat.id,
        "Отправь геолокацию через кнопку ниже.\n"
        "Если ты в Telegram Desktop и отправка недоступна, открой бота на телефоне или вернись в меню.",
        reply_markup=geo_request_menu(),
    )


def start_details_flow(message: types.Message) -> None:
    """Запускает сценарий получения расширенных данных по населённому пункту."""
    user_id = message.from_user.id
    logger.info("Запущен сценарий расширенных данных для пользователя %s.", user_id)

    user_data = load_user(user_id)
    saved_city = user_data.get("city")
    saved_lat = user_data.get("lat")
    saved_lon = user_data.get("lon")

    if saved_lat is not None and saved_lon is not None:
        logger.info(
            "Найдена сохранённая локация для /details у пользователя %s: %s (%s, %s).",
            user_id,
            saved_city,
            saved_lat,
            saved_lon,
        )
        details_saved_drafts[user_id] = {
            "city": saved_city or "Сохранённая локация",
            "lat": saved_lat,
            "lon": saved_lon,
        }
        user_states[user_id] = "waiting_details_use_saved_location"
        bot.send_message(
            message.chat.id,
            f"Использовать последнюю сохранённую локацию: {saved_city or 'Сохранённая локация'}?\n"
            "Ответь: Да или Нет.",
        )
        return

    user_states[user_id] = "waiting_details_city"
    bot.send_message(message.chat.id, "Введи название населённого пункта для расширенных данных.")


def send_details_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
) -> bool:
    """Получает и отправляет расширенные данные по известным координатам."""
    weather = get_current_weather(lat, lon)
    air_components = get_air_pollution(lat, lon)

    if not weather:
        logger.warning(
            "Не удалось получить расширенные данные для пользователя %s (населённый пункт: %s, lat: %s, lon: %s).",
            user_id,
            city_fallback,
            lat,
            lon,
        )
        user_states.pop(user_id, None)
        details_saved_drafts.pop(user_id, None)
        bot.send_message(
            message.chat.id,
            "Не удалось получить расширенные данные. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return False

    location = get_location_by_coordinates(lat, lon)
    if location:
        city_label = build_location_label(location, show_coords=False)
    else:
        city_label = city_fallback

    user_data = load_user(user_id)
    user_data["city"] = city_label
    user_data["lat"] = lat
    user_data["lon"] = lon
    save_user(user_id, user_data)

    answer = format_details_response(city_label, weather, air_components)
    user_states.pop(user_id, None)
    details_saved_drafts.pop(user_id, None)
    bot.send_message(message.chat.id, answer, reply_markup=main_menu())
    return True


def start_compare_flow(message: types.Message) -> None:
    """Запускает сценарий сравнения двух населённых пунктов."""
    user_id = message.from_user.id
    logger.info("Запущен сценарий сравнения населённых пунктов для пользователя %s.", user_id)
    compare_drafts.pop(user_id, None)
    user_states[user_id] = "waiting_compare_city_1"
    bot.send_message(message.chat.id, "Введи первый населённый пункт для сравнения.")


def start_forecast_flow(message: types.Message) -> None:
    """Запускает сценарий прогноза на 5 дней."""
    user_id = message.from_user.id
    logger.info("Запущен сценарий прогноза на 5 дней для пользователя %s.", user_id)

    user_data = load_user(user_id)
    saved_city = user_data.get("city")
    saved_lat = user_data.get("lat")
    saved_lon = user_data.get("lon")

    if saved_lat is not None and saved_lon is not None:
        forecast_saved_drafts[user_id] = {
            "city": saved_city or "Сохранённая локация",
            "lat": saved_lat,
            "lon": saved_lon,
        }
        user_states[user_id] = "waiting_forecast_use_saved_location"
        bot.send_message(
            message.chat.id,
            f"Использовать последнюю сохранённую локацию: {saved_city or 'Сохранённая локация'}?\n"
            "Ответь: Да или Нет.",
        )
        return

    user_states[user_id] = "waiting_forecast_city"
    bot.send_message(message.chat.id, "Введи название населённого пункта для прогноза на 5 дней.")


def group_forecast_by_day(forecast_items: list[dict]) -> dict[str, list[dict]]:
    """Группирует прогноз по календарным дням в формате ДД.ММ."""
    grouped: dict[str, list[dict]] = {}
    for item in forecast_items:
        dt_txt = item.get("dt_txt", "")
        if not dt_txt:
            continue
        date_part = dt_txt.split(" ")[0]
        try:
            day_key = datetime.strptime(date_part, "%Y-%m-%d").strftime("%d.%m")
        except ValueError:
            continue
        grouped.setdefault(day_key, []).append(item)
    return grouped


def build_forecast_days_keyboard(days: list[str]) -> types.InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру с днями прогноза."""
    keyboard = types.InlineKeyboardMarkup()
    for day in days:
        keyboard.add(types.InlineKeyboardButton(text=day, callback_data=f"forecast_day:{day}"))
    keyboard.add(types.InlineKeyboardButton(text="⬅️ В меню", callback_data="forecast_menu"))
    return keyboard


def _forecast_min_temp(day_items: list[dict]) -> float | None:
    """Возвращает минимальную температуру за день."""
    temps = [
        item.get("main", {}).get("temp")
        for item in day_items
        if isinstance(item.get("main", {}).get("temp"), (int, float))
    ]
    return min(temps) if temps else None


def _forecast_max_temp(day_items: list[dict]) -> float | None:
    """Возвращает максимальную температуру за день."""
    temps = [
        item.get("main", {}).get("temp")
        for item in day_items
        if isinstance(item.get("main", {}).get("temp"), (int, float))
    ]
    return max(temps) if temps else None


def _forecast_main_description(day_items: list[dict]) -> str:
    """Определяет самое частое описание погоды за день."""
    descriptions: dict[str, int] = {}
    for item in day_items:
        description = item.get("weather", [{}])[0].get("description", "без описания")
        descriptions[description] = descriptions.get(description, 0) + 1

    if not descriptions:
        return "без описания"

    return max(descriptions, key=descriptions.get)


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


def format_forecast_day(day: str, day_items: list[dict], city_label: str) -> str:
    """Красиво форматирует прогноз одного дня по интервалам 3 часа."""
    min_temp = _forecast_min_temp(day_items)
    max_temp = _forecast_max_temp(day_items)
    main_description = _forecast_main_description(day_items)

    min_text = f"{min_temp:.1f}" if min_temp is not None else "н/д"
    max_text = f"{max_temp:.1f}" if max_temp is not None else "н/д"

    lines = [
        f"📅 Прогноз на {day} для {city_label}",
        "",
        f"🌡 Минимум: {min_text} °C",
        f"🌡 Максимум: {max_text} °C",
        f"☁️ Чаще всего: {main_description}",
        "",
        "🕒 По времени:",
    ]
    for item in day_items:
        dt_txt = item.get("dt_txt", "")
        time_part = dt_txt.split(" ")[1][:5] if " " in dt_txt else "--:--"
        temp = item.get("main", {}).get("temp")
        description = item.get("weather", [{}])[0].get("description", "без описания")
        temp_text = f"{temp:.1f}" if isinstance(temp, (int, float)) else "н/д"
        lines.append(f"• {time_part} — {temp_text}°C, {description}")
    return "\n".join(lines)


def show_forecast_days_message(message: types.Message, user_id: int) -> None:
    """Показывает сообщение со списком дней прогноза."""
    cache = forecast_cache.get(user_id)
    if not cache:
        bot.send_message(
            message.chat.id,
            "Не удалось получить прогноз. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    days = list(cache["grouped"].keys())
    keyboard = build_forecast_days_keyboard(days)
    bot.send_message(
        message.chat.id,
        f"Выбери день прогноза для {cache['city']}:",
        reply_markup=keyboard,
    )


def send_forecast_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    save_location: bool,
) -> bool:
    """Получает прогноз, сохраняет данные в кэш и показывает дни."""
    forecast_items = get_forecast_5d3h(lat, lon)
    if not forecast_items:
        logger.warning(
            "Не удалось получить прогноз для пользователя %s (населённый пункт: %s, lat: %s, lon: %s).",
            user_id,
            city_fallback,
            lat,
            lon,
        )
        user_states.pop(user_id, None)
        forecast_saved_drafts.pop(user_id, None)
        forecast_cache.pop(user_id, None)
        bot.send_message(
            message.chat.id,
            "Не удалось получить прогноз. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return False

    location = get_location_by_coordinates(lat, lon)
    city_label = build_location_label(location, show_coords=False) if location else city_fallback
    grouped = group_forecast_by_day(forecast_items)
    if not grouped:
        logger.warning("Прогноз пришёл пустым после группировки для пользователя %s.", user_id)
        user_states.pop(user_id, None)
        forecast_saved_drafts.pop(user_id, None)
        forecast_cache.pop(user_id, None)
        bot.send_message(
            message.chat.id,
            "Не удалось получить прогноз. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return False

    if save_location:
        user_data = load_user(user_id)
        user_data["city"] = city_label
        user_data["lat"] = lat
        user_data["lon"] = lon
        save_user(user_id, user_data)

    forecast_cache[user_id] = {"city": city_label, "grouped": grouped}
    user_states.pop(user_id, None)
    forecast_saved_drafts.pop(user_id, None)
    show_forecast_days_message(message, user_id)
    return True


def _weather_snapshot(weather: dict) -> dict:
    """Возвращает краткий срез данных погоды для сравнения."""
    main_data = weather.get("main", {})
    weather_data = weather.get("weather", [{}])
    wind_data = weather.get("wind", {})

    return {
        "temp": main_data.get("temp"),
        "feels_like": main_data.get("feels_like"),
        "description": weather_data[0].get("description", "без описания"),
        "humidity": main_data.get("humidity"),
        "wind_speed": wind_data.get("speed"),
        "wind_deg": wind_data.get("deg"),
    }


def _wind_text_from_values(wind_speed: float | None, wind_deg: float | None) -> str:
    """Собирает строку с ветром для ответов."""
    if wind_speed is None:
        return "н/д"
    if wind_deg is None:
        return f"{wind_speed} м/с"
    return f"{wind_speed} м/с, {wind_direction_ru(wind_deg)}"


def format_weather_response(city_label: str, weather: dict) -> str:
    """Собирает текст ответа с текущей погодой."""
    main_data = weather.get("main", {})
    weather_data = weather.get("weather", [{}])
    wind_data = weather.get("wind", {})

    temp = main_data.get("temp")
    feels_like = main_data.get("feels_like")
    description = weather_data[0].get("description", "без описания")
    humidity = main_data.get("humidity")
    pressure = main_data.get("pressure")
    wind_speed = wind_data.get("speed")
    wind_deg = wind_data.get("deg")

    pressure_mmhg = round(pressure * 0.75006) if pressure is not None else None
    wind_text = _wind_text_from_values(wind_speed, wind_deg)

    return (
        f"📍 Населённый пункт: {city_label}\n"
        f"🌡 Температура: {temp if temp is not None else 'н/д'} °C\n"
        f"🤔 Ощущается как: {feels_like if feels_like is not None else 'н/д'} °C\n"
        f"☁️ Описание: {description}\n"
        f"💧 Влажность: {humidity if humidity is not None else 'н/д'}%\n"
        f"🩺 Давление: {pressure_mmhg if pressure_mmhg is not None else 'н/д'} мм рт. ст.\n"
        f"🌬 Ветер: {wind_text}"
    )


def build_location_pick_keyboard(
    locations: list[dict],
    pick_callback_prefix: str,
    cancel_callback_data: str,
) -> types.InlineKeyboardMarkup:
    """
    Универсальная inline-клавиатура выбора населённого пункта из списка геокодинга.

    Подписи на кнопках строятся через build_disambiguated_location_labels: при одинаковых
    названиях к дублям добавляются координаты.

    pick_callback_prefix — префикс callback_data, например «current_pick» или «alerts_pick».
    cancel_callback_data — полное значение callback для кнопки «Отмена».
    """
    keyboard = types.InlineKeyboardMarkup()
    labels = build_disambiguated_location_labels(locations)
    for index, loc in enumerate(locations):
        label = labels[index]
        if len(label) > 64:
            label = label[:61] + "..."
        keyboard.add(
            types.InlineKeyboardButton(
                text=label,
                callback_data=f"{pick_callback_prefix}:{index}",
            )
        )
    keyboard.add(types.InlineKeyboardButton(text="⬅️ Отмена", callback_data=cancel_callback_data))
    return keyboard


def build_current_weather_location_keyboard(locations: list[dict]) -> types.InlineKeyboardMarkup:
    """Inline-клавиатура выбора для сценария «Текущая погода»."""
    return build_location_pick_keyboard(locations, "current_pick", "current_cancel")


def save_user_location_from_geocode_item(user_id: int, location_item: dict) -> bool:
    """Сохраняет city, lat, lon из элемента геокодинга в данные пользователя. Возвращает True при успехе."""
    lat = location_item.get("lat")
    lon = location_item.get("lon")
    city_label = location_item.get("label") or build_location_label(location_item, show_coords=False)

    if lat is None or lon is None:
        return False

    user_data = load_user(user_id)
    user_data["city"] = city_label
    user_data["lat"] = lat
    user_data["lon"] = lon
    save_user(user_id, user_data)
    return True


def complete_current_weather_from_location(
    chat_id: int,
    user_id: int,
    location_item: dict,
) -> None:
    """Загружает текущую погоду по выбранной локации, сохраняет данные и отправляет ответ."""
    lat = location_item.get("lat")
    lon = location_item.get("lon")
    city_label = location_item.get("label") or build_location_label(location_item, show_coords=False)

    if lat is None or lon is None:
        logger.warning("У локации нет координат для пользователя %s.", user_id)
        user_states.pop(user_id, None)
        current_location_choices.pop(user_id, None)
        bot.send_message(
            chat_id,
            "Не удалось получить данные о погоде. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    weather = get_current_weather(lat, lon)
    if not weather:
        logger.warning(
            "Не удалось получить данные о погоде для пользователя %s (lat: %s, lon: %s).",
            user_id,
            lat,
            lon,
        )
        user_states.pop(user_id, None)
        current_location_choices.pop(user_id, None)
        bot.send_message(
            chat_id,
            "Не удалось получить данные о погоде. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    if not save_user_location_from_geocode_item(user_id, location_item):
        user_states.pop(user_id, None)
        current_location_choices.pop(user_id, None)
        bot.send_message(
            chat_id,
            "Не удалось сохранить локацию. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    answer = format_weather_response(city_label, weather)
    logger.info(
        "Успешно получена погода для пользователя %s: %s (lat: %s, lon: %s).",
        user_id,
        city_label,
        lat,
        lon,
    )
    user_states.pop(user_id, None)
    current_location_choices.pop(user_id, None)
    bot.send_message(chat_id, answer, reply_markup=main_menu())


def complete_alerts_location_from_item(chat_id: int, user_id: int, location_item: dict) -> None:
    """Сохраняет локацию из геокодинга для уведомлений и показывает статус."""
    if not save_user_location_from_geocode_item(user_id, location_item):
        logger.warning("Не удалось сохранить локацию уведомлений для пользователя %s.", user_id)
        alerts_location_choices.pop(user_id, None)
        user_states[user_id] = "alerts_menu"
        bot.send_message(
            chat_id,
            "Не удалось сохранить локацию. Попробуй позже.",
            reply_markup=alerts_menu(),
        )
        return

    alerts_location_choices.pop(user_id, None)
    user_states[user_id] = "alerts_menu"
    user_data = ensure_notifications_defaults(load_user(user_id))
    bot.send_message(
        chat_id,
        "✅ Локация для уведомлений обновлена.\n\n" + format_alerts_status(user_data),
        reply_markup=alerts_menu(),
    )


def format_compare_response(city_1: str, weather_1: dict, city_2: str, weather_2: dict) -> str:
    """Собирает текст сравнения двух населённых пунктов."""
    w1 = _weather_snapshot(weather_1)
    w2 = _weather_snapshot(weather_2)

    wind_text_1 = _wind_text_from_values(w1["wind_speed"], w1["wind_deg"])
    wind_text_2 = _wind_text_from_values(w2["wind_speed"], w2["wind_deg"])

    temp_1 = w1["temp"]
    temp_2 = w2["temp"]
    wind_1 = w1["wind_speed"] if w1["wind_speed"] is not None else 0
    wind_2 = w2["wind_speed"] if w2["wind_speed"] is not None else 0

    if temp_1 is None or temp_2 is None:
        temp_summary = "По температуре недостаточно данных для точного сравнения."
    elif temp_1 == temp_2:
        temp_summary = "Температура в обоих населённых пунктах одинаковая."
    elif temp_1 > temp_2:
        temp_summary = f"Теплее в населённом пункте {city_1}."
    else:
        temp_summary = f"Теплее в населённом пункте {city_2}."

    if wind_1 == wind_2:
        wind_summary = "Скорость ветра в обоих населённых пунктах одинаковая."
    elif wind_1 > wind_2:
        wind_summary = f"Сильнее ветер в населённом пункте {city_1}."
    else:
        wind_summary = f"Сильнее ветер в населённом пункте {city_2}."

    return (
        "🏙 Сравнение населённых пунктов\n\n"
        f"1) {city_1}\n"
        f"🌡 Температура: {w1['temp'] if w1['temp'] is not None else 'н/д'} °C\n"
        f"🤔 Ощущается как: {w1['feels_like'] if w1['feels_like'] is not None else 'н/д'} °C\n"
        f"☁️ Описание: {w1['description']}\n"
        f"💧 Влажность: {w1['humidity'] if w1['humidity'] is not None else 'н/д'}%\n"
        f"🌬 Ветер: {wind_text_1}\n\n"
        f"2) {city_2}\n"
        f"🌡 Температура: {w2['temp'] if w2['temp'] is not None else 'н/д'} °C\n"
        f"🤔 Ощущается как: {w2['feels_like'] if w2['feels_like'] is not None else 'н/д'} °C\n"
        f"☁️ Описание: {w2['description']}\n"
        f"💧 Влажность: {w2['humidity'] if w2['humidity'] is not None else 'н/д'}%\n"
        f"🌬 Ветер: {wind_text_2}\n\n"
        f"📌 Итог:\n• {temp_summary}\n• {wind_summary}"
    )


def _format_hh_mm_from_unix(unix_ts: int | None) -> str:
    """Преобразует unix timestamp в формат ЧЧ:ММ."""
    if unix_ts is None:
        return "н/д"
    return datetime.fromtimestamp(unix_ts).strftime("%H:%M")


def _format_visibility(visibility_meters: int | float | None) -> str:
    """Возвращает видимость в метрах или километрах в удобном формате."""
    if visibility_meters is None:
        return "н/д"

    try:
        value = float(visibility_meters)
    except (TypeError, ValueError):
        return str(visibility_meters)

    if value < 1000:
        return f"{int(value)} м"
    return f"{value / 1000:.1f} км"


def _format_air_component_value(value: object) -> str:
    """Форматирует значение компонента воздуха до 1 знака, если это число."""
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return str(value)


def format_details_response(city_label: str, weather: dict, air_components: dict | None) -> str:
    """Собирает текст ответа с расширенными данными о погоде и воздухе."""
    main_data = weather.get("main", {})
    weather_data = weather.get("weather", [{}])
    wind_data = weather.get("wind", {})
    clouds_data = weather.get("clouds", {})
    sys_data = weather.get("sys", {})

    temp = main_data.get("temp")
    feels_like = main_data.get("feels_like")
    description = weather_data[0].get("description", "без описания")
    humidity = main_data.get("humidity")
    pressure = main_data.get("pressure")
    pressure_mmhg = round(pressure * 0.75006) if pressure is not None else None
    wind_speed = wind_data.get("speed")
    wind_deg = wind_data.get("deg")
    clouds = clouds_data.get("all")
    visibility = weather.get("visibility")
    sunrise = _format_hh_mm_from_unix(sys_data.get("sunrise"))
    sunset = _format_hh_mm_from_unix(sys_data.get("sunset"))

    if wind_speed is None:
        wind_text = "н/д"
    elif wind_deg is None:
        wind_text = f"{wind_speed} м/с"
    else:
        wind_text = f"{wind_speed} м/с, {wind_direction_ru(wind_deg)}"

    lines = [
        f"📍 Населённый пункт: {city_label}",
        f"🌡 Температура: {temp if temp is not None else 'н/д'} °C",
        f"🤔 Ощущается как: {feels_like if feels_like is not None else 'н/д'} °C",
        f"☁️ Описание: {description}",
        f"💧 Влажность: {humidity if humidity is not None else 'н/д'}%",
        f"🩺 Давление: {pressure_mmhg if pressure_mmhg is not None else 'н/д'} мм рт. ст.",
        f"🌬 Ветер: {wind_text}",
        f"🌥 Облачность: {clouds if clouds is not None else 'н/д'}%",
        f"👀 Видимость: {_format_visibility(visibility)}",
        f"🌅 Восход солнца: {sunrise}",
        f"🌇 Закат солнца: {sunset}",
    ]

    if not air_components:
        lines.append("🌫 Данные о качестве воздуха недоступны.")
        return "\n".join(lines)

    air_analysis = analyze_air_pollution(air_components, extended=True)
    lines.append(f"🌫 Качество воздуха: {air_analysis.get('overall_status', 'Нет данных')}")
    details = air_analysis.get("details")

    if isinstance(details, dict):
        for component in details.values():
            name = component.get("name", "Компонент")
            value = _format_air_component_value(component.get("value", "н/д"))
            status = component.get("status", "Нет данных")
            lines.append(f"• {name} — {value} мкг/м³ ({status})")
    else:
        lines.append(str(details))

    return "\n".join(lines)


def main_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт главное меню бота."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Текущая погода"), types.KeyboardButton("Прогноз на 5 дней"))
    keyboard.row(types.KeyboardButton("Моя геолокация"), types.KeyboardButton("Сравнить города"))
    keyboard.row(types.KeyboardButton("Расширенные данные"), types.KeyboardButton("Уведомления"))
    keyboard.row(types.KeyboardButton("Помощь"))
    return keyboard


def geo_request_menu() -> types.ReplyKeyboardMarkup:
    """Создаёт клавиатуру для запроса геолокации."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("Отправить геолокацию", request_location=True))
    keyboard.row(types.KeyboardButton("⬅️ В меню"))
    return keyboard


@bot.message_handler(commands=["start"])
def handle_start(message: types.Message) -> None:
    """Обрабатывает команду /start."""
    logger.info("Получена команда /start от пользователя %s.", message.from_user.id)
    user_states.pop(message.from_user.id, None)
    current_location_choices.pop(message.from_user.id, None)
    alerts_location_choices.pop(message.from_user.id, None)
    text = (
        "Привет! Я Weather Teller 🌤\n\n"
        "Помогу:\n"
        "• узнать текущую погоду\n"
        "• посмотреть прогноз на 5 дней\n"
        "• получить погоду по геолокации\n"
        "• сравнить города\n"
        "• посмотреть расширенные данные и качество воздуха\n\n"
        "Выбери действие ниже или используй команды через Menu."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())


@bot.message_handler(commands=["help"])
def handle_help(message: types.Message) -> None:
    """Показывает справку по командам."""
    logger.info("Получена команда /help от пользователя %s.", message.from_user.id)
    bot.send_message(message.chat.id, help_text(), reply_markup=main_menu())


@bot.message_handler(commands=["current"])
def handle_current(message: types.Message) -> None:
    """Запускает сценарий текущей погоды через slash-команду."""
    logger.info("Получена команда /current от пользователя %s.", message.from_user.id)
    start_current_weather_flow(message)


@bot.message_handler(commands=["forecast"])
def handle_forecast(message: types.Message) -> None:
    """Запускает сценарий прогноза на 5 дней через slash-команду."""
    logger.info("Получена команда /forecast от пользователя %s.", message.from_user.id)
    start_forecast_flow(message)


@bot.message_handler(commands=["geo"])
def handle_geo(message: types.Message) -> None:
    """Запускает сценарий погоды по геолокации через slash-команду."""
    logger.info("Получена команда /geo от пользователя %s.", message.from_user.id)
    start_geo_weather_flow(message)


@bot.message_handler(commands=["details"])
def handle_details(message: types.Message) -> None:
    """Запускает сценарий расширенных данных через slash-команду."""
    logger.info("Получена команда /details от пользователя %s.", message.from_user.id)
    start_details_flow(message)


@bot.message_handler(commands=["compare"])
def handle_compare(message: types.Message) -> None:
    """Запускает сценарий сравнения населённых пунктов через slash-команду."""
    logger.info("Получена команда /compare от пользователя %s.", message.from_user.id)
    start_compare_flow(message)


@bot.message_handler(commands=["alerts"])
def handle_alerts(message: types.Message) -> None:
    """Запускает сценарий уведомлений через slash-команду."""
    logger.info("Получена команда /alerts от пользователя %s.", message.from_user.id)
    start_alerts_flow(message)


@bot.message_handler(func=lambda message: message.text in MENU_BUTTONS)
def handle_menu_buttons(message: types.Message) -> None:
    """Обрабатывает нажатия кнопок главного меню."""
    section_name = message.text
    logger.info("Пользователь %s нажал кнопку меню: %s", message.from_user.id, section_name)

    if section_name == "Текущая погода":
        start_current_weather_flow(message)
        return
    if section_name == "Прогноз на 5 дней":
        start_forecast_flow(message)
        return

    if section_name == "Помощь":
        bot.send_message(message.chat.id, help_text(), reply_markup=main_menu())
        return
    if section_name == "Моя геолокация":
        start_geo_weather_flow(message)
        return
    if section_name == "Расширенные данные":
        start_details_flow(message)
        return
    if section_name == "Сравнить города":
        start_compare_flow(message)
        return
    if section_name == "Уведомления":
        start_alerts_flow(message)
        return

    bot.send_message(
        message.chat.id,
        f"Раздел '{section_name}' уже в работе. Скоро подключим.",
        reply_markup=main_menu(),
    )


@bot.message_handler(func=lambda message: message.text == "⬅️ В меню")
def handle_back_to_menu(message: types.Message) -> None:
    """Возвращает пользователя в меню уведомлений или в главное меню."""
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state in {
        "waiting_alerts_location_menu",
        "waiting_alerts_location_text",
        "waiting_alerts_location_pick",
        "waiting_alerts_location_geo",
    }:
        alerts_location_choices.pop(user_id, None)
        user_states[user_id] = "alerts_menu"
        user_data = ensure_notifications_defaults(load_user(user_id))
        bot.send_message(
            message.chat.id,
            format_alerts_status(user_data),
            reply_markup=alerts_menu(),
        )
        return

    user_states.pop(user_id, None)
    compare_drafts.pop(user_id, None)
    details_saved_drafts.pop(user_id, None)
    forecast_saved_drafts.pop(user_id, None)
    forecast_cache.pop(user_id, None)
    current_location_choices.pop(user_id, None)
    alerts_location_choices.pop(user_id, None)
    bot.send_message(message.chat.id, "Главное меню.", reply_markup=main_menu())


@bot.message_handler(content_types=["location"])
def handle_location_message(message: types.Message) -> None:
    """Обрабатывает геолокацию от пользователя."""
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state == "waiting_alerts_location_geo":
        alerts_location_choices.pop(user_id, None)
        location_data = message.location
        lat = location_data.latitude
        lon = location_data.longitude
        logger.info(
            "Получена геолокация для уведомлений от пользователя %s: lat=%s, lon=%s.",
            user_id,
            lat,
            lon,
        )
        location = get_location_by_coordinates(lat, lon)
        if location:
            city_label = build_location_label(location, show_coords=False)
        else:
            city_label = "Выбранная геолокация"

        user_data = load_user(user_id)
        user_data["city"] = city_label
        user_data["lat"] = lat
        user_data["lon"] = lon
        save_user(user_id, user_data)

        user_states[user_id] = "alerts_menu"
        user_data = ensure_notifications_defaults(load_user(user_id))
        bot.send_message(
            message.chat.id,
            "✅ Локация для уведомлений обновлена.\n\n" + format_alerts_status(user_data),
            reply_markup=alerts_menu(),
        )
        return

    current_location_choices.pop(user_id, None)
    location_data = message.location
    lat = location_data.latitude
    lon = location_data.longitude
    logger.info(
        "Получена геолокация от пользователя %s: lat=%s, lon=%s.",
        user_id,
        lat,
        lon,
    )

    weather = get_current_weather(lat, lon)
    if not weather:
        logger.warning(
            "Не удалось получить погоду по геолокации для пользователя %s (lat=%s, lon=%s).",
            user_id,
            lat,
            lon,
        )
        user_states.pop(user_id, None)
        bot.send_message(
            message.chat.id,
            "Не удалось получить данные о погоде по геолокации. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    location = get_location_by_coordinates(lat, lon)
    if location:
        city_label = build_location_label(location, show_coords=False)
    else:
        city_label = "Выбранная геолокация"

    user_data = load_user(user_id)
    user_data["city"] = city_label
    user_data["lat"] = lat
    user_data["lon"] = lon
    save_user(user_id, user_data)

    answer = format_weather_response(city_label, weather)
    logger.info(
        "Успешно получена погода по геолокации для пользователя %s: %s (lat=%s, lon=%s).",
        user_id,
        city_label,
        lat,
        lon,
    )
    user_states.pop(user_id, None)
    bot.send_message(message.chat.id, answer, reply_markup=main_menu())


@bot.callback_query_handler(func=lambda call: call.data.startswith("current_"))
def handle_current_weather_location_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации или отмену в сценарии «Текущая погода»."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "current_cancel":
        current_location_choices.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Выбор отменён.", reply_markup=main_menu())
        return

    if call.data.startswith("current_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            current_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        choices = current_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            current_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        location_item = build_geocode_item_with_disambiguated_label(choices, index)
        logger.info(
            "Пользователь %s выбрал вариант текущей погоды #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        bot.answer_callback_query(call.id)
        complete_current_weather_from_location(chat_id, user_id, location_item)
        return

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("alerts_"))
def handle_alerts_location_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации для уведомлений (inline) или отмену."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "alerts_cancel":
        alerts_location_choices.pop(user_id, None)
        user_states[user_id] = "alerts_menu"
        user_data = ensure_notifications_defaults(load_user(user_id))
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, format_alerts_status(user_data), reply_markup=alerts_menu())
        return

    if call.data.startswith("alerts_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id)
            alerts_location_choices.pop(user_id, None)
            user_states[user_id] = "alerts_menu"
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=alerts_menu(),
            )
            return

        choices = alerts_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            bot.answer_callback_query(call.id)
            alerts_location_choices.pop(user_id, None)
            user_states[user_id] = "alerts_menu"
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=alerts_menu(),
            )
            return

        location_item = build_geocode_item_with_disambiguated_label(choices, index)
        logger.info(
            "Пользователь %s выбрал локацию для уведомлений #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        bot.answer_callback_query(call.id)
        complete_alerts_location_from_item(chat_id, user_id, location_item)
        return

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("forecast_"))
def handle_forecast_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает inline-навигацию прогноза."""
    user_id = call.from_user.id
    cache = forecast_cache.get(user_id)
    if not cache:
        bot.answer_callback_query(call.id, "Данные прогноза устарели.")
        return

    if call.data == "forecast_back":
        days = list(cache["grouped"].keys())
        keyboard = build_forecast_days_keyboard(days)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Выбери день прогноза для {cache['city']}:",
            reply_markup=keyboard,
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == "forecast_menu":
        user_states.pop(user_id, None)
        forecast_saved_drafts.pop(user_id, None)
        forecast_cache.pop(user_id, None)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Главное меню.",
        )
        bot.send_message(call.message.chat.id, "Главное меню.", reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("forecast_day:"):
        day = call.data.split(":", 1)[1]
        logger.info("Пользователь %s выбрал день прогноза: %s", user_id, day)
        day_items = cache["grouped"].get(day)
        if not day_items:
            bot.answer_callback_query(call.id, "День прогноза не найден.")
            return

        text = format_forecast_day(day, day_items, cache["city"])
        keyboard = build_forecast_day_keyboard(list(cache["grouped"].keys()), day)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
        )
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message: True)
def handle_unknown_text(message: types.Message) -> None:
    """Обрабатывает неизвестный текст."""
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state == "waiting_current_weather_city":
        query = (message.text or "").strip()
        logger.info("Пользователь %s ввёл запрос для текущей погоды: %s", user_id, query)
        if not query:
            logger.info("Пустой ввод для текущей погоды: пользователь %s.", user_id)
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        locations = get_locations(query, limit=5)
        if not locations:
            logger.info("Населённый пункт не найден для пользователя %s: %s", user_id, query)
            bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return

        if len(locations) == 1:
            complete_current_weather_from_location(message.chat.id, user_id, locations[0])
            return

        current_location_choices[user_id] = locations
        user_states[user_id] = "waiting_current_weather_pick"
        logger.info(
            "Найдено несколько вариантов (%s) для пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_current_weather_location_keyboard(locations),
        )
        return

    if state == "waiting_current_weather_pick":
        if not current_location_choices.get(user_id):
            user_states.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return
        bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return

    if state == "waiting_alerts_location_text":
        query = (message.text or "").strip()
        logger.info("Пользователь %s ввёл запрос локации для уведомлений: %s", user_id, query)
        if not query:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        locations = get_locations(query, limit=5)
        if not locations:
            bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return

        if len(locations) == 1:
            complete_alerts_location_from_item(message.chat.id, user_id, locations[0])
            return

        alerts_location_choices[user_id] = locations
        user_states[user_id] = "waiting_alerts_location_pick"
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_location_pick_keyboard(locations, "alerts_pick", "alerts_cancel"),
        )
        return

    if state == "waiting_alerts_location_pick":
        if not alerts_location_choices.get(user_id):
            user_states[user_id] = "alerts_menu"
            user_data = ensure_notifications_defaults(load_user(user_id))
            bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=alerts_menu(),
            )
            return
        bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return

    if state == "waiting_alerts_location_geo":
        bot.send_message(
            message.chat.id,
            "Пожалуйста, отправь геолокацию через кнопку ниже или вернись в меню.",
            reply_markup=geo_request_menu(),
        )
        return

    if state == "waiting_alerts_location_menu":
        if message.text == "Ввести населённый пункт":
            user_states[user_id] = "waiting_alerts_location_text"
            bot.send_message(
                message.chat.id,
                "Введи населённый пункт для уведомлений.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return
        if message.text == "Отправить геолокацию":
            user_states[user_id] = "waiting_alerts_location_geo"
            bot.send_message(
                message.chat.id,
                "Отправь геолокацию для уведомлений.",
                reply_markup=geo_request_menu(),
            )
            return
        bot.send_message(
            message.chat.id,
            "Выбери действие кнопкой ниже или нажми «⬅️ В меню», чтобы вернуться в меню уведомлений.",
            reply_markup=alerts_location_menu(),
        )
        return

    if state == "waiting_geo_location":
        if message.text == "⬅️ В меню":
            user_states.pop(user_id, None)
            compare_drafts.pop(user_id, None)
            bot.send_message(message.chat.id, "Главное меню.", reply_markup=main_menu())
            return

        bot.send_message(
            message.chat.id,
            "Пожалуйста, отправь геолокацию через кнопку ниже.\n"
            "Если ты используешь Telegram Desktop, открой бота на телефоне или вернись в меню.",
            reply_markup=geo_request_menu(),
        )
        return

    if state == "waiting_details_city":
        city = (message.text or "").strip()
        logger.info("Пользователь %s ввёл населённый пункт для расширенных данных: %s", user_id, city)
        if not city:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        coordinates = get_coordinates(city)
        if not coordinates:
            logger.info("Населённый пункт не найден для расширенных данных у пользователя %s: %s", user_id, city)
            bot.send_message(message.chat.id, "⚠️ Населённый пункт не найден. Попробуй ввести другое название.")
            return

        lat, lon = coordinates
        if send_details_by_coordinates(message, user_id, lat, lon, city):
            logger.info(
                "Успешно получены расширенные данные для пользователя %s по введённому населённому пункту %s.",
                user_id,
                city,
            )
        return

    if state == "waiting_details_use_saved_location":
        answer = (message.text or "").strip().lower()

        yes_values = {"да", "д", "yes", "y"}
        no_values = {"нет", "н", "no"}

        if answer in yes_values:
            logger.info("Пользователь %s выбрал: Да (использовать сохранённую локацию).", user_id)
            draft = details_saved_drafts.get(user_id)
            if not draft:
                user_states[user_id] = "waiting_details_city"
                bot.send_message(message.chat.id, "Введи название населённого пункта для расширенных данных.")
                return

            if send_details_by_coordinates(
                message,
                user_id,
                draft["lat"],
                draft["lon"],
                draft["city"],
            ):
                logger.info(
                    "Успешно получены расширенные данные по сохранённой локации для пользователя %s.",
                    user_id,
                )
            return

        if answer in no_values:
            logger.info("Пользователь %s выбрал: Нет (ввести новый населённый пункт).", user_id)
            details_saved_drafts.pop(user_id, None)
            user_states[user_id] = "waiting_details_city"
            bot.send_message(message.chat.id, "Введи название населённого пункта для расширенных данных.")
            return

        bot.send_message(message.chat.id, "Пожалуйста, ответь: Да или Нет.")
        return

    if state == "waiting_forecast_use_saved_location":
        answer = (message.text or "").strip().lower()
        yes_values = {"да", "д", "yes", "y"}
        no_values = {"нет", "н", "no"}

        if answer in yes_values:
            logger.info("Пользователь %s выбрал: Да (прогноз по сохранённой локации).", user_id)
            draft = forecast_saved_drafts.get(user_id)
            if not draft:
                user_states[user_id] = "waiting_forecast_city"
                bot.send_message(message.chat.id, "Введи название населённого пункта для прогноза на 5 дней.")
                return

            if send_forecast_by_coordinates(
                message,
                user_id,
                draft["lat"],
                draft["lon"],
                draft["city"],
                save_location=False,
            ):
                logger.info(
                    "Успешно получен прогноз по сохранённой локации для пользователя %s.",
                    user_id,
                )
            return

        if answer in no_values:
            logger.info("Пользователь %s выбрал: Нет (ввести населённый пункт для прогноза).", user_id)
            forecast_saved_drafts.pop(user_id, None)
            user_states[user_id] = "waiting_forecast_city"
            bot.send_message(message.chat.id, "Введи название населённого пункта для прогноза на 5 дней.")
            return

        bot.send_message(message.chat.id, "Пожалуйста, ответь: Да или Нет.")
        return

    if state == "waiting_forecast_city":
        city = (message.text or "").strip()
        logger.info("Пользователь %s ввёл населённый пункт для прогноза: %s", user_id, city)
        if not city:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        coordinates = get_coordinates(city)
        if not coordinates:
            bot.send_message(message.chat.id, "⚠️ Населённый пункт не найден. Попробуй ввести другое название.")
            return

        lat, lon = coordinates
        if send_forecast_by_coordinates(
            message,
            user_id,
            lat,
            lon,
            city,
            save_location=True,
        ):
            logger.info("Успешно получен прогноз для пользователя %s по населённому пункту %s.", user_id, city)
        return

    if state in {"alerts_menu", "waiting_alerts_interval"}:
        user_data = load_user(user_id)
        user_data = ensure_notifications_defaults(user_data)

        if message.text == "Показать статус":
            bot.send_message(message.chat.id, format_alerts_status(user_data), reply_markup=alerts_menu())
            return

        if message.text == "Изменить локацию":
            user_states[user_id] = "waiting_alerts_location_menu"
            bot.send_message(
                message.chat.id,
                "Выбери способ указания локации для уведомлений:",
                reply_markup=alerts_location_menu(),
            )
            return

        if message.text == "Включить уведомления":
            user_data["notifications"]["enabled"] = True
            save_user(user_id, user_data)
            logger.info("Пользователь %s включил уведомления.", user_id)
            user_states[user_id] = "alerts_menu"
            bot.send_message(message.chat.id, "✅ Уведомления включены.", reply_markup=alerts_menu())
            return

        if message.text == "Выключить уведомления":
            user_data["notifications"]["enabled"] = False
            save_user(user_id, user_data)
            logger.info("Пользователь %s выключил уведомления.", user_id)
            user_states[user_id] = "alerts_menu"
            bot.send_message(message.chat.id, "✅ Уведомления выключены.", reply_markup=alerts_menu())
            return

        if message.text == "Изменить интервал":
            user_states[user_id] = "waiting_alerts_interval"
            bot.send_message(
                message.chat.id,
                "Введи интервал проверки в часах, например: 2",
                reply_markup=alerts_menu(),
            )
            return

        if state == "waiting_alerts_interval":
            try:
                interval = int((message.text or "").strip())
            except ValueError:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Введите положительное число часов.",
                    reply_markup=alerts_menu(),
                )
                return

            if interval <= 0:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Введите положительное число часов.",
                    reply_markup=alerts_menu(),
                )
                return

            user_data["notifications"]["interval_h"] = interval
            save_user(user_id, user_data)
            logger.info("Пользователь %s изменил интервал уведомлений на %s ч.", user_id, interval)
            user_states[user_id] = "alerts_menu"
            bot.send_message(
                message.chat.id,
                f"✅ Интервал обновлён: {interval} ч.",
                reply_markup=alerts_menu(),
            )
            return

        bot.send_message(
            message.chat.id,
            "Выбери действие в меню уведомлений.",
            reply_markup=alerts_menu(),
        )
        return

    if state == "waiting_compare_city_1":
        city_1 = (message.text or "").strip()
        logger.info("Пользователь %s ввёл первый населённый пункт для сравнения: %s", user_id, city_1)
        if not city_1:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        coordinates_1 = get_coordinates(city_1)
        if not coordinates_1:
            bot.send_message(message.chat.id, "⚠️ Населённый пункт не найден. Попробуй ввести другое название.")
            return

        compare_drafts[user_id] = {"city_1_input": city_1, "coordinates_1": coordinates_1}
        user_states[user_id] = "waiting_compare_city_2"
        bot.send_message(message.chat.id, "Теперь введи второй населённый пункт.")
        return

    if state == "waiting_compare_city_2":
        city_2 = (message.text or "").strip()
        logger.info("Пользователь %s ввёл второй населённый пункт для сравнения: %s", user_id, city_2)
        if not city_2:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        coordinates_2 = get_coordinates(city_2)
        if not coordinates_2:
            bot.send_message(message.chat.id, "⚠️ Населённый пункт не найден. Попробуй ввести другое название.")
            return

        draft = compare_drafts.get(user_id)
        if not draft:
            user_states.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                "Не удалось получить данные для сравнения. Попробуй позже.",
                reply_markup=main_menu(),
            )
            return

        lat_1, lon_1 = draft["coordinates_1"]
        lat_2, lon_2 = coordinates_2

        weather_1 = get_current_weather(lat_1, lon_1)
        weather_2 = get_current_weather(lat_2, lon_2)

        if not weather_1 or not weather_2:
            logger.warning(
                "Не удалось получить данные для сравнения у пользователя %s.",
                user_id,
            )
            user_states.pop(user_id, None)
            compare_drafts.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                "Не удалось получить данные для сравнения. Попробуй позже.",
                reply_markup=main_menu(),
            )
            return

        location_1 = get_location_by_coordinates(lat_1, lon_1)
        location_2 = get_location_by_coordinates(lat_2, lon_2)

        city_label_1 = (
            build_location_label(location_1, show_coords=False)
            if location_1
            else draft["city_1_input"]
        )
        city_label_2 = (
            build_location_label(location_2, show_coords=False)
            if location_2
            else city_2
        )

        answer = format_compare_response(city_label_1, weather_1, city_label_2, weather_2)
        logger.info(
            "Успешно выполнено сравнение для пользователя %s: %s vs %s.",
            user_id,
            city_label_1,
            city_label_2,
        )
        user_states.pop(user_id, None)
        compare_drafts.pop(user_id, None)
        bot.send_message(message.chat.id, answer, reply_markup=main_menu())
        return

    bot.send_message(
        message.chat.id,
        "Не понял команду. Используй /start или кнопки меню.",
        reply_markup=main_menu(),
    )


if __name__ == "__main__":
    try:
        logger.info("Запуск бота.")
        threading.Thread(target=alerts_worker, daemon=True).start()
        bot.infinity_polling(skip_pending=True)
    except KeyboardInterrupt:
        print("Бот остановлен пользователем.")
