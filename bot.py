import os
import logging
import time
import threading
from types import SimpleNamespace
from dotenv import load_dotenv
import telebot
from telebot import types
from weather_app import (
    get_coordinates,
    get_locations,
    get_current_weather,
    get_forecast_5d3h,
    get_air_pollution,
    build_geocode_item_with_disambiguated_label,
    build_location_label,
    get_location_by_coordinates,
)
from keyboards import (
    add_saved_location_menu,
    alerts_location_menu,
    alerts_menu,
    build_current_weather_location_keyboard,
    build_favorite_pick_keyboard,
    build_forecast_day_keyboard,
    build_forecast_days_keyboard,
    build_location_pick_keyboard,
    build_saved_locations_keyboard,
    build_scenario_location_choice_keyboard,
    geo_request_menu,
    locations_menu,
    main_menu,
)
from formatters import (
    format_alerts_status,
    format_compare_response,
    format_details_response,
    format_saved_locations,
    format_weather_response,
    help_text,
)
from forecast_service import group_forecast_by_day, format_forecast_day
from alerts_service import ensure_notifications_defaults, detect_weather_alerts
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
# Варианты локаций для расширенных данных / прогноза / сравнения (несколько совпадений геокодинга)
details_location_choices = {}
forecast_location_choices = {}
# Для сравнения: {"step": 1|2, "locations": list[dict]}
compare_location_choices = {}
# Черновики и варианты для сценария «Добавить новую локацию» в разделе «Мои локации»
saved_location_drafts = {}
# Черновик для сценария «Переименовать локацию»: хранит выбранный location_id
rename_location_drafts = {}

MENU_BUTTONS = [
    "Текущая погода",
    "Прогноз на 5 дней",
    "Моя геолокация",
    "Сравнить города",
    "Расширенные данные",
    "Мои локации",
    "Уведомления",
    "Помощь",
]


def save_saved_location_item(user_id: int, title: str, label: str, lat: float, lon: float) -> None:
    """Сохраняет локацию в список пользователя или обновляет title у дубля по координатам."""
    user_data = load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list):
        saved_locations = []

    existing_location = None
    for item in saved_locations:
        if not isinstance(item, dict):
            continue
        item_lat = item.get("lat")
        item_lon = item.get("lon")
        if item_lat is None or item_lon is None:
            continue
        if abs(float(item_lat) - float(lat)) < 1e-6 and abs(float(item_lon) - float(lon)) < 1e-6:
            existing_location = item
            break

    if existing_location is not None:
        existing_location["title"] = title
        existing_location["label"] = label
        existing_location["lat"] = float(lat)
        existing_location["lon"] = float(lon)
    else:
        location_id = f"loc_{int(time.time() * 1000)}_{len(saved_locations) + 1}"
        saved_locations.append(
            {
                "id": location_id,
                "title": title,
                "label": label,
                "lat": float(lat),
                "lon": float(lon),
            }
        )

    user_data["saved_locations"] = saved_locations
    save_user(user_id, user_data)


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


def start_locations_flow(message: types.Message) -> None:
    """Открывает раздел управления сохранёнными локациями."""
    user_id = message.from_user.id
    logger.info("Пользователь %s вошёл в раздел сохранённых локаций.", user_id)
    saved_location_drafts.pop(user_id, None)
    rename_location_drafts.pop(user_id, None)
    user_states[user_id] = "locations_menu"
    bot.send_message(
        message.chat.id,
        "Раздел сохранённых локаций.\nВыбери действие:",
        reply_markup=locations_menu(),
    )


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
    details_location_choices.pop(user_id, None)

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
    *,
    preferred_city_label: str | None = None,
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
        details_location_choices.pop(user_id, None)
        bot.send_message(
            message.chat.id,
            "Не удалось получить расширенные данные. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return False

    # Приоритет у подписи, которую пользователь уже выбрал/сохранил вручную.
    if preferred_city_label:
        city_label = preferred_city_label
    elif city_fallback:
        city_label = city_fallback
    else:
        location = get_location_by_coordinates(lat, lon)
        city_label = build_location_label(location, show_coords=False) if location else "Выбранная локация"

    user_data = load_user(user_id)
    user_data["city"] = city_label
    user_data["lat"] = lat
    user_data["lon"] = lon
    save_user(user_id, user_data)

    answer = format_details_response(city_label, weather, air_components)
    user_states.pop(user_id, None)
    details_saved_drafts.pop(user_id, None)
    details_location_choices.pop(user_id, None)
    bot.send_message(message.chat.id, answer, reply_markup=main_menu())
    return True


def start_compare_flow(message: types.Message) -> None:
    """Запускает сценарий сравнения двух населённых пунктов."""
    user_id = message.from_user.id
    logger.info("Запущен сценарий сравнения населённых пунктов для пользователя %s.", user_id)
    compare_drafts.pop(user_id, None)
    compare_location_choices.pop(user_id, None)
    user_states[user_id] = "waiting_compare_city_1"
    bot.send_message(message.chat.id, "Введи первый населённый пункт для сравнения.")


def start_forecast_flow(message: types.Message) -> None:
    """Запускает сценарий прогноза на 5 дней."""
    user_id = message.from_user.id
    logger.info("Запущен сценарий прогноза на 5 дней для пользователя %s.", user_id)
    forecast_location_choices.pop(user_id, None)

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
    preferred_city_label: str | None = None,
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
        forecast_location_choices.pop(user_id, None)
        bot.send_message(
            message.chat.id,
            "Не удалось получить прогноз. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return False

    # Приоритет у подписи, которую пользователь уже выбрал/сохранил вручную.
    if preferred_city_label:
        city_label = preferred_city_label
    elif city_fallback:
        city_label = city_fallback
    else:
        location = get_location_by_coordinates(lat, lon)
        city_label = build_location_label(location, show_coords=False) if location else "Выбранная локация"
    grouped = group_forecast_by_day(forecast_items)
    if not grouped:
        logger.warning("Прогноз пришёл пустым после группировки для пользователя %s.", user_id)
        user_states.pop(user_id, None)
        forecast_saved_drafts.pop(user_id, None)
        forecast_cache.pop(user_id, None)
        forecast_location_choices.pop(user_id, None)
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
    forecast_location_choices.pop(user_id, None)
    show_forecast_days_message(message, user_id)
    return True


def _message_stub_for_chat(chat_id: int) -> SimpleNamespace:
    """Заглушка сообщения с chat.id для вызовов send_* из обработчиков callback."""
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id))


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


def complete_compare_two_locations(
    chat_id: int,
    user_id: int,
    lat_1: float,
    lon_1: float,
    city_label_1: str,
    lat_2: float,
    lon_2: float,
    city_label_2: str,
) -> None:
    """Загружает погоду по двум точкам и отправляет текст сравнения."""
    weather_1 = get_current_weather(lat_1, lon_1)
    weather_2 = get_current_weather(lat_2, lon_2)

    if not weather_1 or not weather_2:
        logger.warning("Не удалось получить данные для сравнения у пользователя %s.", user_id)
        user_states.pop(user_id, None)
        compare_drafts.pop(user_id, None)
        compare_location_choices.pop(user_id, None)
        bot.send_message(
            chat_id,
            "Не удалось получить данные для сравнения. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    answer = format_compare_response(city_label_1, weather_1, city_label_2, weather_2)
    logger.info(
        "Успешно выполнено сравнение для пользователя %s: %s vs %s.",
        user_id,
        city_label_1,
        city_label_2,
    )
    user_states.pop(user_id, None)
    compare_drafts.pop(user_id, None)
    compare_location_choices.pop(user_id, None)
    bot.send_message(chat_id, answer, reply_markup=main_menu())


@bot.message_handler(commands=["start"])
def handle_start(message: types.Message) -> None:
    """Обрабатывает команду /start."""
    logger.info("Получена команда /start от пользователя %s.", message.from_user.id)
    user_states.pop(message.from_user.id, None)
    current_location_choices.pop(message.from_user.id, None)
    alerts_location_choices.pop(message.from_user.id, None)
    details_location_choices.pop(message.from_user.id, None)
    forecast_location_choices.pop(message.from_user.id, None)
    compare_location_choices.pop(message.from_user.id, None)
    saved_location_drafts.pop(message.from_user.id, None)
    rename_location_drafts.pop(message.from_user.id, None)
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


@bot.message_handler(commands=["locations"])
def handle_locations(message: types.Message) -> None:
    """Открывает раздел сохранённых и любимых локаций."""
    logger.info("Получена команда /locations от пользователя %s.", message.from_user.id)
    start_locations_flow(message)


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
    if section_name == "Мои локации":
        start_locations_flow(message)
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
    details_location_choices.pop(user_id, None)
    forecast_location_choices.pop(user_id, None)
    compare_location_choices.pop(user_id, None)
    saved_location_drafts.pop(user_id, None)
    rename_location_drafts.pop(user_id, None)
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

    if state == "waiting_new_saved_location_geo":
        location_data = message.location
        lat = location_data.latitude
        lon = location_data.longitude
        location = get_location_by_coordinates(lat, lon)
        if location:
            label = build_location_label(location, show_coords=False)
        else:
            label = "Выбранная геолокация"

        saved_location_drafts[user_id] = {
            "lat": float(lat),
            "lon": float(lon),
            "label": label,
        }
        user_states[user_id] = "waiting_new_saved_location_title"
        bot.send_message(
            message.chat.id,
            "Введи название для этой локации, например: Дом",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    current_location_choices.pop(user_id, None)
    details_location_choices.pop(user_id, None)
    forecast_location_choices.pop(user_id, None)
    compare_location_choices.pop(user_id, None)
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


@bot.callback_query_handler(func=lambda call: call.data.startswith("details_"))
def handle_details_location_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации для расширенных данных (inline) или отмену."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "details_cancel":
        details_location_choices.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Выбор отменён.", reply_markup=main_menu())
        return

    if call.data.startswith("details_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            details_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        choices = details_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            details_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        location_item = build_geocode_item_with_disambiguated_label(choices, index)
        logger.info(
            "Пользователь %s выбрал локацию для расширенных данных #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        bot.answer_callback_query(call.id)
        stub = _message_stub_for_chat(chat_id)
        city = location_item.get("label") or build_location_label(location_item, show_coords=False)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        if lat is None or lon is None:
            details_location_choices.pop(user_id, None)
            user_states.pop(user_id, None)
            bot.send_message(
                chat_id,
                "Не удалось получить расширенные данные. Попробуй позже.",
                reply_markup=main_menu(),
            )
            return
        send_details_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        return

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("compare_pick:") or call.data == "compare_cancel"
)
def handle_compare_location_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор населённого пункта при сравнении (inline) или отмену."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "compare_cancel":
        compare_location_choices.pop(user_id, None)
        compare_drafts.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Выбор отменён.", reply_markup=main_menu())
        return

    parts = call.data.split(":")
    if len(parts) != 3 or parts[0] != "compare_pick":
        bot.answer_callback_query(call.id)
        return

    try:
        step = int(parts[1])
        index = int(parts[2])
    except ValueError:
        bot.answer_callback_query(call.id)
        compare_location_choices.pop(user_id, None)
        compare_drafts.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.send_message(
            chat_id,
            "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
            reply_markup=main_menu(),
        )
        return

    meta = compare_location_choices.get(user_id)
    if not meta or not isinstance(meta.get("locations"), list):
        bot.answer_callback_query(call.id)
        compare_location_choices.pop(user_id, None)
        compare_drafts.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.send_message(
            chat_id,
            "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
            reply_markup=main_menu(),
        )
        return

    if meta.get("step") != step:
        bot.answer_callback_query(call.id)
        compare_location_choices.pop(user_id, None)
        compare_drafts.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.send_message(
            chat_id,
            "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
            reply_markup=main_menu(),
        )
        return

    locations = meta["locations"]
    if index < 0 or index >= len(locations):
        bot.answer_callback_query(call.id)
        compare_location_choices.pop(user_id, None)
        compare_drafts.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.send_message(
            chat_id,
            "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
            reply_markup=main_menu(),
        )
        return

    location_item = build_geocode_item_with_disambiguated_label(locations, index)
    lat = location_item.get("lat")
    lon = location_item.get("lon")
    if lat is None or lon is None:
        bot.answer_callback_query(call.id)
        compare_location_choices.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.send_message(
            chat_id,
            "Не удалось получить данные для сравнения. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    city_label = location_item.get("label") or build_location_label(location_item, show_coords=False)
    logger.info(
        "Пользователь %s выбрал населённый пункт для сравнения (шаг %s) #%s: %s",
        user_id,
        step,
        index,
        city_label,
    )
    bot.answer_callback_query(call.id)

    if step == 1:
        compare_drafts[user_id] = {
            "coordinates_1": (float(lat), float(lon)),
            "city_1_input": city_label,
            "city_1_label": city_label,
        }
        compare_location_choices.pop(user_id, None)
        user_states[user_id] = "waiting_compare_city_2"
        bot.send_message(chat_id, "Теперь введи второй населённый пункт.")
        return

    if step == 2:
        draft = compare_drafts.get(user_id)
        if not draft or "coordinates_1" not in draft:
            compare_location_choices.pop(user_id, None)
            compare_drafts.pop(user_id, None)
            user_states.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        lat_1, lon_1 = draft["coordinates_1"]
        city_label_1 = draft.get("city_1_label") or draft.get("city_1_input") or "Первый населённый пункт"
        complete_compare_two_locations(
            chat_id,
            user_id,
            lat_1,
            lon_1,
            city_label_1,
            float(lat),
            float(lon),
            city_label,
        )
        return


@bot.callback_query_handler(func=lambda call: call.data.startswith("favorite_pick:"))
def handle_favorite_pick_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор основной локации из списка сохранённых."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    location_id = call.data.split(":", 1)[1] if ":" in call.data else ""
    if not location_id:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Не удалось выбрать основную локацию.", reply_markup=locations_menu())
        return

    user_data = load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Сохранённых локаций пока нет.", reply_markup=locations_menu())
        return

    location_exists = any(
        isinstance(item, dict) and item.get("id") == location_id
        for item in saved_locations
    )
    if not location_exists:
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            "⚠️ Выбранная локация не найдена. Попробуй снова.",
            reply_markup=locations_menu(),
        )
        return

    user_data["favorite_location_id"] = location_id
    save_user(user_id, user_data)
    user_states[user_id] = "locations_menu"
    logger.info("Пользователь %s выбрал основную локацию: %s", user_id, location_id)

    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id,
        "✅ Основная локация обновлена.\n\n" + format_saved_locations(user_data),
        reply_markup=locations_menu(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_location_pick:"))
def handle_delete_location_pick_callback(call: types.CallbackQuery) -> None:
    """Удаляет выбранную сохранённую локацию."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    location_id = call.data.split(":", 1)[1] if ":" in call.data else ""

    if not location_id:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Не удалось удалить локацию.", reply_markup=locations_menu())
        return

    user_data = load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Сохранённых локаций пока нет.", reply_markup=locations_menu())
        return

    filtered_locations = [
        item
        for item in saved_locations
        if not (isinstance(item, dict) and item.get("id") == location_id)
    ]

    if len(filtered_locations) == len(saved_locations):
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Выбранная локация не найдена.", reply_markup=locations_menu())
        return

    user_data["saved_locations"] = filtered_locations
    if user_data.get("favorite_location_id") == location_id:
        user_data["favorite_location_id"] = None
    save_user(user_id, user_data)
    user_states[user_id] = "locations_menu"
    rename_location_drafts.pop(user_id, None)

    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id,
        "✅ Локация удалена.\n\n" + format_saved_locations(user_data),
        reply_markup=locations_menu(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("rename_location_pick:"))
def handle_rename_location_pick_callback(call: types.CallbackQuery) -> None:
    """Запоминает выбранную локацию и запрашивает новое имя."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    location_id = call.data.split(":", 1)[1] if ":" in call.data else ""

    if not location_id:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Не удалось выбрать локацию.", reply_markup=locations_menu())
        return

    user_data = load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Сохранённых локаций пока нет.", reply_markup=locations_menu())
        return

    location_exists = any(
        isinstance(item, dict) and item.get("id") == location_id
        for item in saved_locations
    )
    if not location_exists:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Выбранная локация не найдена.", reply_markup=locations_menu())
        return

    rename_location_drafts[user_id] = {"location_id": location_id}
    user_states[user_id] = "waiting_rename_location_title"
    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id,
        "Введи новое название для локации.",
        reply_markup=types.ReplyKeyboardRemove(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("savedloc_"))
def handle_saved_location_pick_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации при добавлении новой сохранённой локации."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "savedloc_cancel":
        saved_location_drafts.pop(user_id, None)
        user_states[user_id] = "locations_menu"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Выбор отменён.", reply_markup=locations_menu())
        return

    if call.data.startswith("savedloc_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            saved_location_drafts.pop(user_id, None)
            user_states[user_id] = "locations_menu"
            bot.answer_callback_query(call.id)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return

        draft = saved_location_drafts.get(user_id)
        locations = draft.get("locations") if isinstance(draft, dict) else None
        if not isinstance(locations, list) or index < 0 or index >= len(locations):
            saved_location_drafts.pop(user_id, None)
            user_states[user_id] = "locations_menu"
            bot.answer_callback_query(call.id)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return

        location_item = build_geocode_item_with_disambiguated_label(locations, index)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        label = location_item.get("label") or build_location_label(location_item, show_coords=False)
        if lat is None or lon is None:
            saved_location_drafts.pop(user_id, None)
            user_states[user_id] = "locations_menu"
            bot.answer_callback_query(call.id)
            bot.send_message(
                chat_id,
                "Не удалось определить локацию. Попробуй снова.",
                reply_markup=locations_menu(),
            )
            return

        saved_location_drafts[user_id] = {
            "lat": float(lat),
            "lon": float(lon),
            "label": label,
        }
        user_states[user_id] = "waiting_new_saved_location_title"
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            "Введи название для этой локации, например: Дом",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("forecast_"))
def handle_forecast_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает inline-навигацию прогноза и выбор локации перед прогнозом."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "forecast_cancel":
        forecast_location_choices.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Выбор отменён.", reply_markup=main_menu())
        return

    if call.data.startswith("forecast_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            forecast_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        choices = forecast_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            forecast_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        location_item = build_geocode_item_with_disambiguated_label(choices, index)
        logger.info(
            "Пользователь %s выбрал локацию для прогноза #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        bot.answer_callback_query(call.id)
        stub = _message_stub_for_chat(chat_id)
        city = location_item.get("label") or build_location_label(location_item, show_coords=False)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        if lat is None or lon is None:
            forecast_location_choices.pop(user_id, None)
            user_states.pop(user_id, None)
            bot.send_message(
                chat_id,
                "Не удалось получить прогноз. Попробуй позже.",
                reply_markup=main_menu(),
            )
            return
        send_forecast_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            save_location=True,
            preferred_city_label=city,
        )
        return

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

    if state == "waiting_location_title":
        title = (message.text or "").strip()
        if not title:
            bot.send_message(message.chat.id, "⚠️ Введи название локации, например: Дом")
            return

        user_data = load_user(user_id)
        current_city = user_data.get("city")
        current_lat = user_data.get("lat")
        current_lon = user_data.get("lon")

        if current_lat is None or current_lon is None or not current_city:
            user_states[user_id] = "locations_menu"
            bot.send_message(
                message.chat.id,
                "Сначала нужно получить погоду или выбрать локацию.",
                reply_markup=locations_menu(),
            )
            return

        save_saved_location_item(
            user_id=user_id,
            title=title,
            label=current_city,
            lat=float(current_lat),
            lon=float(current_lon),
        )
        user_states[user_id] = "locations_menu"
        logger.info("Пользователь %s сохранил локацию с title=%s.", user_id, title)
        bot.send_message(message.chat.id, "✅ Локация сохранена.", reply_markup=locations_menu())
        return

    if state == "waiting_new_saved_location_title":
        title = (message.text or "").strip()
        if not title:
            bot.send_message(message.chat.id, "⚠️ Введи название локации, например: Дом")
            return

        draft = saved_location_drafts.get(user_id)
        if not isinstance(draft, dict):
            user_states[user_id] = "locations_menu"
            bot.send_message(
                message.chat.id,
                "⚠️ Данные локации устарели. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return

        lat = draft.get("lat")
        lon = draft.get("lon")
        label = draft.get("label")
        if lat is None or lon is None or not label:
            saved_location_drafts.pop(user_id, None)
            user_states[user_id] = "locations_menu"
            bot.send_message(
                message.chat.id,
                "⚠️ Данные локации устарели. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return

        save_saved_location_item(
            user_id=user_id,
            title=title,
            label=str(label),
            lat=float(lat),
            lon=float(lon),
        )
        saved_location_drafts.pop(user_id, None)
        user_states[user_id] = "locations_menu"
        logger.info("Пользователь %s добавил новую сохранённую локацию с title=%s.", user_id, title)
        bot.send_message(
            message.chat.id,
            "✅ Локация сохранена.",
            reply_markup=locations_menu(),
        )
        return

    if state == "waiting_rename_location_title":
        new_title = (message.text or "").strip()
        if not new_title:
            bot.send_message(message.chat.id, "⚠️ Введи новое название локации.")
            return

        draft = rename_location_drafts.get(user_id)
        location_id = draft.get("location_id") if isinstance(draft, dict) else None
        if not isinstance(location_id, str) or not location_id:
            rename_location_drafts.pop(user_id, None)
            user_states[user_id] = "locations_menu"
            bot.send_message(
                message.chat.id,
                "⚠️ Данные для переименования устарели. Попробуй снова.",
                reply_markup=locations_menu(),
            )
            return

        user_data = load_user(user_id)
        saved_locations = user_data.get("saved_locations", [])
        if not isinstance(saved_locations, list) or not saved_locations:
            rename_location_drafts.pop(user_id, None)
            user_states[user_id] = "locations_menu"
            bot.send_message(
                message.chat.id,
                "Сохранённых локаций пока нет.",
                reply_markup=locations_menu(),
            )
            return

        target_location = next(
            (item for item in saved_locations if isinstance(item, dict) and item.get("id") == location_id),
            None,
        )
        if not isinstance(target_location, dict):
            rename_location_drafts.pop(user_id, None)
            user_states[user_id] = "locations_menu"
            bot.send_message(
                message.chat.id,
                "⚠️ Выбранная локация не найдена.",
                reply_markup=locations_menu(),
            )
            return

        target_location["title"] = new_title
        user_data["saved_locations"] = saved_locations
        save_user(user_id, user_data)
        rename_location_drafts.pop(user_id, None)
        user_states[user_id] = "locations_menu"
        bot.send_message(
            message.chat.id,
            "✅ Название локации обновлено.",
            reply_markup=locations_menu(),
        )
        return

    if state == "locations_menu":
        if message.text == "Сохранить текущую локацию":
            user_data = load_user(user_id)
            city = user_data.get("city")
            lat = user_data.get("lat")
            lon = user_data.get("lon")
            if lat is None or lon is None or not city:
                bot.send_message(
                    message.chat.id,
                    "Сначала нужно получить погоду или выбрать локацию.",
                    reply_markup=locations_menu(),
                )
                return

            user_states[user_id] = "waiting_location_title"
            bot.send_message(
                message.chat.id,
                "Введи название для этой локации, например: Дом",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return

        if message.text == "Добавить новую локацию":
            saved_location_drafts.pop(user_id, None)
            rename_location_drafts.pop(user_id, None)
            user_states[user_id] = "waiting_new_saved_location_menu"
            bot.send_message(
                message.chat.id,
                "Выбери способ добавления новой локации:",
                reply_markup=add_saved_location_menu(),
            )
            return

        if message.text == "Показать мои локации":
            user_data = load_user(user_id)
            bot.send_message(
                message.chat.id,
                format_saved_locations(user_data),
                reply_markup=locations_menu(),
            )
            return

        if message.text == "Сделать основной":
            user_data = load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=locations_menu(),
                )
                return

            bot.send_message(
                message.chat.id,
                "Выбери основную локацию:",
                reply_markup=build_favorite_pick_keyboard(saved_locations),
            )
            return

        if message.text == "Удалить локацию":
            user_data = load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=locations_menu(),
                )
                return
            bot.send_message(
                message.chat.id,
                "Выбери локацию для удаления:",
                reply_markup=build_saved_locations_keyboard(saved_locations, "delete_location_pick"),
            )
            return

        if message.text == "Переименовать локацию":
            user_data = load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=locations_menu(),
                )
                return
            bot.send_message(
                message.chat.id,
                "Выбери локацию для переименования:",
                reply_markup=build_saved_locations_keyboard(saved_locations, "rename_location_pick"),
            )
            return

        bot.send_message(
            message.chat.id,
            "Выбери действие в разделе локаций или нажми «⬅️ В меню».",
            reply_markup=locations_menu(),
        )
        return

    if state == "waiting_new_saved_location_menu":
        if message.text == "Ввести населённый пункт":
            user_states[user_id] = "waiting_new_saved_location_text"
            bot.send_message(
                message.chat.id,
                "Введи населённый пункт, который хочешь сохранить.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return

        if message.text == "Отправить геолокацию":
            user_states[user_id] = "waiting_new_saved_location_geo"
            bot.send_message(
                message.chat.id,
                "Отправь геолокацию, которую хочешь сохранить.",
                reply_markup=geo_request_menu(),
            )
            return

        bot.send_message(
            message.chat.id,
            "Выбери действие кнопкой ниже или нажми «⬅️ В меню».",
            reply_markup=add_saved_location_menu(),
        )
        return

    if state == "waiting_new_saved_location_text":
        query = (message.text or "").strip()
        if not query:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        locations = get_locations(query, limit=5)
        if not locations:
            bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее.",
            )
            return

        if len(locations) == 1:
            location_item = build_geocode_item_with_disambiguated_label(locations, 0)
            lat = location_item.get("lat")
            lon = location_item.get("lon")
            label = location_item.get("label") or build_location_label(location_item, show_coords=False)
            if lat is None or lon is None:
                user_states[user_id] = "locations_menu"
                bot.send_message(
                    message.chat.id,
                    "Не удалось определить локацию. Попробуй снова.",
                    reply_markup=locations_menu(),
                )
                return
            saved_location_drafts[user_id] = {
                "lat": float(lat),
                "lon": float(lon),
                "label": label,
            }
            user_states[user_id] = "waiting_new_saved_location_title"
            bot.send_message(
                message.chat.id,
                "Введи название для этой локации, например: Дом",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return

        saved_location_drafts[user_id] = {"locations": locations}
        user_states[user_id] = "waiting_new_saved_location_pick"
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_location_pick_keyboard(locations, "savedloc_pick", "savedloc_cancel"),
        )
        return

    if state == "waiting_new_saved_location_pick":
        draft = saved_location_drafts.get(user_id)
        if not isinstance(draft, dict) or not isinstance(draft.get("locations"), list):
            user_states[user_id] = "locations_menu"
            saved_location_drafts.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return
        bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return

    if state == "waiting_new_saved_location_geo":
        bot.send_message(
            message.chat.id,
            "Отправь геолокацию, которую хочешь сохранить.",
            reply_markup=geo_request_menu(),
        )
        return

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
            details_location_choices.pop(user_id, None)
            forecast_location_choices.pop(user_id, None)
            compare_location_choices.pop(user_id, None)
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
        query = (message.text or "").strip()
        logger.info("Пользователь %s ввёл населённый пункт для расширенных данных: %s", user_id, query)
        if not query:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        locations = get_locations(query, limit=5)
        if not locations:
            logger.info("Населённый пункт не найден для расширенных данных у пользователя %s: %s", user_id, query)
            bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return

        if len(locations) == 1:
            loc = build_geocode_item_with_disambiguated_label(locations, 0)
            lat = loc.get("lat")
            lon = loc.get("lon")
            city = loc.get("label") or build_location_label(loc, show_coords=False)
            if lat is None or lon is None:
                bot.send_message(
                    message.chat.id,
                    "Не удалось получить расширенные данные. Попробуй позже.",
                    reply_markup=main_menu(),
                )
                return
            if send_details_by_coordinates(
                message,
                user_id,
                float(lat),
                float(lon),
                city,
                preferred_city_label=city,
            ):
                logger.info(
                    "Успешно получены расширенные данные для пользователя %s по введённому населённому пункту %s.",
                    user_id,
                    query,
                )
            return

        details_location_choices[user_id] = locations
        user_states[user_id] = "waiting_details_pick"
        logger.info(
            "Найдено несколько вариантов (%s) для расширенных данных у пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_scenario_location_choice_keyboard(locations, "details"),
        )
        return

    if state == "waiting_details_pick":
        if not details_location_choices.get(user_id):
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
                preferred_city_label=draft["city"],
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
                preferred_city_label=draft["city"],
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
        query = (message.text or "").strip()
        logger.info("Пользователь %s ввёл населённый пункт для прогноза: %s", user_id, query)
        if not query:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        locations = get_locations(query, limit=5)
        if not locations:
            bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом.",
            )
            return

        if len(locations) == 1:
            loc = build_geocode_item_with_disambiguated_label(locations, 0)
            lat = loc.get("lat")
            lon = loc.get("lon")
            city = loc.get("label") or build_location_label(loc, show_coords=False)
            if lat is None or lon is None:
                bot.send_message(
                    message.chat.id,
                    "Не удалось получить прогноз. Попробуй позже.",
                    reply_markup=main_menu(),
                )
                return
            if send_forecast_by_coordinates(
                message,
                user_id,
                float(lat),
                float(lon),
                city,
                save_location=True,
                preferred_city_label=city,
            ):
                logger.info("Успешно получен прогноз для пользователя %s по населённому пункту %s.", user_id, query)
            return

        forecast_location_choices[user_id] = locations
        user_states[user_id] = "waiting_forecast_pick"
        logger.info(
            "Найдено несколько вариантов (%s) для прогноза у пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_scenario_location_choice_keyboard(locations, "forecast"),
        )
        return

    if state == "waiting_forecast_pick":
        if not forecast_location_choices.get(user_id):
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
        query = (message.text or "").strip()
        logger.info("Пользователь %s ввёл первый населённый пункт для сравнения: %s", user_id, query)
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
            loc = build_geocode_item_with_disambiguated_label(locations, 0)
            lat = loc.get("lat")
            lon = loc.get("lon")
            label = loc.get("label") or build_location_label(loc, show_coords=False)
            if lat is None or lon is None:
                bot.send_message(
                    message.chat.id,
                    "Не удалось получить данные для сравнения. Попробуй позже.",
                    reply_markup=main_menu(),
                )
                return
            compare_drafts[user_id] = {
                "coordinates_1": (float(lat), float(lon)),
                "city_1_input": label,
                "city_1_label": label,
            }
            user_states[user_id] = "waiting_compare_city_2"
            bot.send_message(message.chat.id, "Теперь введи второй населённый пункт.")
            return

        compare_location_choices[user_id] = {"step": 1, "locations": locations}
        user_states[user_id] = "waiting_compare_location_pick"
        logger.info(
            "Найдено несколько вариантов (%s) для первого населённого пункта у пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_scenario_location_choice_keyboard(locations, "compare", compare_step=1),
        )
        return

    if state == "waiting_compare_city_2":
        query = (message.text or "").strip()
        logger.info("Пользователь %s ввёл второй населённый пункт для сравнения: %s", user_id, query)
        if not query:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return

        draft = compare_drafts.get(user_id)
        if not draft or "coordinates_1" not in draft:
            user_states.pop(user_id, None)
            compare_drafts.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                "Не удалось получить данные для сравнения. Попробуй позже.",
                reply_markup=main_menu(),
            )
            return

        locations = get_locations(query, limit=5)
        if not locations:
            bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return

        if len(locations) == 1:
            loc = build_geocode_item_with_disambiguated_label(locations, 0)
            lat_2 = loc.get("lat")
            lon_2 = loc.get("lon")
            city_label_2 = loc.get("label") or build_location_label(loc, show_coords=False)
            if lat_2 is None or lon_2 is None:
                user_states.pop(user_id, None)
                compare_drafts.pop(user_id, None)
                bot.send_message(
                    message.chat.id,
                    "Не удалось получить данные для сравнения. Попробуй позже.",
                    reply_markup=main_menu(),
                )
                return
            lat_1, lon_1 = draft["coordinates_1"]
            city_label_1 = draft.get("city_1_label") or draft.get("city_1_input") or "Первый населённый пункт"
            complete_compare_two_locations(
                message.chat.id,
                user_id,
                lat_1,
                lon_1,
                city_label_1,
                float(lat_2),
                float(lon_2),
                city_label_2,
            )
            return

        compare_location_choices[user_id] = {"step": 2, "locations": locations}
        user_states[user_id] = "waiting_compare_location_pick"
        logger.info(
            "Найдено несколько вариантов (%s) для второго населённого пункта у пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_scenario_location_choice_keyboard(locations, "compare", compare_step=2),
        )
        return

    if state == "waiting_compare_location_pick":
        if not compare_location_choices.get(user_id):
            user_states.pop(user_id, None)
            compare_drafts.pop(user_id, None)
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

    bot.send_message(
        message.chat.id,
        "Не понял команду. Используй /start или кнопки меню.",
        reply_markup=main_menu(),
    )


if __name__ == "__main__":
    try:
        process_id = os.getpid()
        # Если появляются дубли ответов, сначала проверь, не запущены ли два экземпляра бота одновременно.
        logger.info("Запуск бота. PID процесса: %s", process_id)
        alerts_thread = threading.Thread(target=alerts_worker, daemon=True)
        alerts_thread.start()
        logger.info("Фоновый поток alerts_worker запущен (PID=%s).", process_id)
        logger.info("Старт polling (PID=%s).", process_id)
        bot.infinity_polling(skip_pending=True)
    except KeyboardInterrupt:
        print("Бот остановлен пользователем.")
