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
from locations_service import (
    complete_alerts_location_from_item,
    complete_current_weather_from_location,
    save_saved_location_item,
)
from handlers.current import handle_current_text
from handlers.details import handle_details_text
from handlers.forecast import handle_forecast_text
from handlers.compare import handle_compare_text
from handlers.alerts import handle_alerts_text
from handlers.locations import handle_locations_text
from handlers.geo import handle_geo_text
from handlers.callbacks_current import handle_current_weather_callback
from handlers.callbacks_alerts import handle_alerts_location_callback as handle_alerts_callback_logic
from handlers.callbacks_compare import handle_compare_location_callback as handle_compare_callback_logic
from handlers.callbacks_locations import (
    handle_delete_location_pick_callback as handle_delete_location_callback_logic,
    handle_favorite_pick_callback as handle_favorite_callback_logic,
    handle_rename_location_pick_callback as handle_rename_location_callback_logic,
    handle_saved_location_pick_callback as handle_saved_location_callback_logic,
)
from handlers.callbacks_forecast import handle_forecast_callback as handle_forecast_callback_logic
from handlers.states import (
    ALERTS_STATES,
    COMPARE_STATES,
    CURRENT_STATES,
    DETAILS_STATES,
    FORECAST_STATES,
    LOCATIONS_STATES,
    ALERTS_MENU,
    LOCATIONS_MENU,
    WAITING_ALERTS_INTERVAL,
    WAITING_ALERTS_LOCATION_GEO,
    WAITING_ALERTS_LOCATION_MENU,
    WAITING_ALERTS_LOCATION_PICK,
    WAITING_ALERTS_LOCATION_TEXT,
    WAITING_COMPARE_CITY_1,
    WAITING_COMPARE_CITY_2,
    WAITING_COMPARE_LOCATION_PICK,
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_DETAILS_CITY,
    WAITING_DETAILS_PICK,
    WAITING_DETAILS_USE_SAVED_LOCATION,
    WAITING_FORECAST_CITY,
    WAITING_FORECAST_PICK,
    WAITING_FORECAST_USE_SAVED_LOCATION,
    WAITING_GEO_LOCATION,
    WAITING_LOCATION_TITLE,
    WAITING_NEW_SAVED_LOCATION_GEO,
    WAITING_NEW_SAVED_LOCATION_MENU,
    WAITING_NEW_SAVED_LOCATION_PICK,
    WAITING_NEW_SAVED_LOCATION_TEXT,
    WAITING_NEW_SAVED_LOCATION_TITLE,
    WAITING_RENAME_LOCATION_TITLE,
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

    user_states[user_id] = ALERTS_MENU
    bot.send_message(message.chat.id, format_alerts_status(user_data), reply_markup=alerts_menu())


def start_locations_flow(message: types.Message) -> None:
    """Открывает раздел управления сохранёнными локациями."""
    user_id = message.from_user.id
    logger.info("Пользователь %s вошёл в раздел сохранённых локаций.", user_id)
    saved_location_drafts.pop(user_id, None)
    rename_location_drafts.pop(user_id, None)
    user_states[user_id] = LOCATIONS_MENU
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
    user_states[user_id] = WAITING_CURRENT_WEATHER_CITY
    bot.send_message(message.chat.id, "Введи название населённого пункта.")


def start_geo_weather_flow(message: types.Message) -> None:
    """Запускает сценарий получения погоды по геолокации."""
    logger.info("Запущен сценарий геолокации для пользователя %s.", message.from_user.id)
    user_states[message.from_user.id] = WAITING_GEO_LOCATION
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
        user_states[user_id] = WAITING_DETAILS_USE_SAVED_LOCATION
        bot.send_message(
            message.chat.id,
            f"Использовать последнюю сохранённую локацию: {saved_city or 'Сохранённая локация'}?\n"
            "Ответь: Да или Нет.",
        )
        return

    user_states[user_id] = WAITING_DETAILS_CITY
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
    user_states[user_id] = WAITING_COMPARE_CITY_1
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
        user_states[user_id] = WAITING_FORECAST_USE_SAVED_LOCATION
        bot.send_message(
            message.chat.id,
            f"Использовать последнюю сохранённую локацию: {saved_city or 'Сохранённая локация'}?\n"
            "Ответь: Да или Нет.",
        )
        return

    user_states[user_id] = WAITING_FORECAST_CITY
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
        WAITING_ALERTS_LOCATION_MENU,
        WAITING_ALERTS_LOCATION_TEXT,
        WAITING_ALERTS_LOCATION_PICK,
        WAITING_ALERTS_LOCATION_GEO,
    }:
        alerts_location_choices.pop(user_id, None)
        user_states[user_id] = ALERTS_MENU
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

    if state == WAITING_ALERTS_LOCATION_GEO:
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

        user_states[user_id] = ALERTS_MENU
        user_data = ensure_notifications_defaults(load_user(user_id))
        bot.send_message(
            message.chat.id,
            "✅ Локация для уведомлений обновлена.\n\n" + format_alerts_status(user_data),
            reply_markup=alerts_menu(),
        )
        return

    if state == WAITING_NEW_SAVED_LOCATION_GEO:
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
        user_states[user_id] = WAITING_NEW_SAVED_LOCATION_TITLE
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
    handle_current_weather_callback(
        call,
        bot=bot,
        logger=logger,
        user_states=user_states,
        current_location_choices=current_location_choices,
        complete_current_weather_from_location=complete_current_weather_from_location,
        main_menu=main_menu,
        build_geocode_item_with_disambiguated_label=build_geocode_item_with_disambiguated_label,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("alerts_"))
def handle_alerts_location_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации для уведомлений (inline) или отмену."""
    handle_alerts_callback_logic(
        call,
        bot=bot,
        logger=logger,
        user_states=user_states,
        alerts_location_choices=alerts_location_choices,
        ALERTS_MENU=ALERTS_MENU,
        load_user=load_user,
        ensure_notifications_defaults=ensure_notifications_defaults,
        format_alerts_status=format_alerts_status,
        alerts_menu=alerts_menu,
        build_geocode_item_with_disambiguated_label=build_geocode_item_with_disambiguated_label,
        complete_alerts_location_from_item=complete_alerts_location_from_item,
    )


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
    handle_compare_callback_logic(
        call,
        bot=bot,
        logger=logger,
        user_states=user_states,
        compare_drafts=compare_drafts,
        compare_location_choices=compare_location_choices,
        WAITING_COMPARE_CITY_2=WAITING_COMPARE_CITY_2,
        build_geocode_item_with_disambiguated_label=build_geocode_item_with_disambiguated_label,
        build_location_label=build_location_label,
        complete_compare_two_locations=complete_compare_two_locations,
        main_menu=main_menu,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("favorite_pick:"))
def handle_favorite_pick_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор основной локации из списка сохранённых."""
    handle_favorite_callback_logic(
        call,
        bot=bot,
        logger=logger,
        user_states=user_states,
        LOCATIONS_MENU=LOCATIONS_MENU,
        load_user=load_user,
        save_user=save_user,
        format_saved_locations=format_saved_locations,
        locations_menu=locations_menu,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_location_pick:"))
def handle_delete_location_pick_callback(call: types.CallbackQuery) -> None:
    """Удаляет выбранную сохранённую локацию."""
    handle_delete_location_callback_logic(
        call,
        bot=bot,
        user_states=user_states,
        rename_location_drafts=rename_location_drafts,
        LOCATIONS_MENU=LOCATIONS_MENU,
        load_user=load_user,
        save_user=save_user,
        format_saved_locations=format_saved_locations,
        locations_menu=locations_menu,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("rename_location_pick:"))
def handle_rename_location_pick_callback(call: types.CallbackQuery) -> None:
    """Запоминает выбранную локацию и запрашивает новое имя."""
    handle_rename_location_callback_logic(
        call,
        bot=bot,
        user_states=user_states,
        rename_location_drafts=rename_location_drafts,
        LOCATIONS_MENU=LOCATIONS_MENU,
        WAITING_RENAME_LOCATION_TITLE=WAITING_RENAME_LOCATION_TITLE,
        load_user=load_user,
        locations_menu=locations_menu,
        types=types,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("savedloc_"))
def handle_saved_location_pick_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации при добавлении новой сохранённой локации."""
    handle_saved_location_callback_logic(
        call,
        bot=bot,
        user_states=user_states,
        saved_location_drafts=saved_location_drafts,
        LOCATIONS_MENU=LOCATIONS_MENU,
        WAITING_NEW_SAVED_LOCATION_TITLE=WAITING_NEW_SAVED_LOCATION_TITLE,
        build_geocode_item_with_disambiguated_label=build_geocode_item_with_disambiguated_label,
        build_location_label=build_location_label,
        locations_menu=locations_menu,
        types=types,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("forecast_"))
def handle_forecast_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает inline-навигацию прогноза и выбор локации перед прогнозом."""
    handle_forecast_callback_logic(
        call,
        bot=bot,
        logger=logger,
        user_states=user_states,
        forecast_saved_drafts=forecast_saved_drafts,
        forecast_location_choices=forecast_location_choices,
        forecast_cache=forecast_cache,
        _message_stub_for_chat=_message_stub_for_chat,
        build_geocode_item_with_disambiguated_label=build_geocode_item_with_disambiguated_label,
        build_location_label=build_location_label,
        send_forecast_by_coordinates=send_forecast_by_coordinates,
        main_menu=main_menu,
        build_forecast_days_keyboard=build_forecast_days_keyboard,
        build_forecast_day_keyboard=build_forecast_day_keyboard,
        format_forecast_day=format_forecast_day,
    )


@bot.message_handler(func=lambda message: True)
def handle_unknown_text(message: types.Message) -> None:
    """Маршрутизирует текст в сценарный обработчик по текущему состоянию."""
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state in LOCATIONS_STATES and handle_locations_text(
        message,
        user_id,
        state,
        bot=bot,
        logger=logger,
        user_states=user_states,
        saved_location_drafts=saved_location_drafts,
        rename_location_drafts=rename_location_drafts,
        load_user=load_user,
        save_user=save_user,
        save_saved_location_item=save_saved_location_item,
        format_saved_locations=format_saved_locations,
        locations_menu=locations_menu,
        add_saved_location_menu=add_saved_location_menu,
        build_saved_locations_keyboard=build_saved_locations_keyboard,
        build_favorite_pick_keyboard=build_favorite_pick_keyboard,
        build_location_pick_keyboard=build_location_pick_keyboard,
        geo_request_menu=geo_request_menu,
    ):
        return

    if state in CURRENT_STATES and handle_current_text(
        message,
        user_id,
        state,
        bot=bot,
        logger=logger,
        user_states=user_states,
        current_location_choices=current_location_choices,
        complete_current_weather_from_location=complete_current_weather_from_location,
        main_menu=main_menu,
        build_current_weather_location_keyboard=build_current_weather_location_keyboard,
    ):
        return

    if state in DETAILS_STATES and handle_details_text(
        message,
        user_id,
        state,
        bot=bot,
        logger=logger,
        user_states=user_states,
        details_saved_drafts=details_saved_drafts,
        details_location_choices=details_location_choices,
        send_details_by_coordinates=send_details_by_coordinates,
        main_menu=main_menu,
        build_scenario_location_choice_keyboard=build_scenario_location_choice_keyboard,
    ):
        return

    if state in FORECAST_STATES and handle_forecast_text(
        message,
        user_id,
        state,
        bot=bot,
        logger=logger,
        user_states=user_states,
        forecast_saved_drafts=forecast_saved_drafts,
        forecast_location_choices=forecast_location_choices,
        send_forecast_by_coordinates=send_forecast_by_coordinates,
        main_menu=main_menu,
        build_scenario_location_choice_keyboard=build_scenario_location_choice_keyboard,
    ):
        return

    if state in ALERTS_STATES and handle_alerts_text(
        message,
        user_id,
        state,
        bot=bot,
        logger=logger,
        user_states=user_states,
        alerts_location_choices=alerts_location_choices,
        load_user=load_user,
        save_user=save_user,
        ensure_notifications_defaults=ensure_notifications_defaults,
        complete_alerts_location_from_item=complete_alerts_location_from_item,
        format_alerts_status=format_alerts_status,
        alerts_menu=alerts_menu,
        alerts_location_menu=alerts_location_menu,
        build_location_pick_keyboard=build_location_pick_keyboard,
        geo_request_menu=geo_request_menu,
    ):
        return

    if state in COMPARE_STATES and handle_compare_text(
        message,
        user_id,
        state,
        bot=bot,
        logger=logger,
        user_states=user_states,
        compare_drafts=compare_drafts,
        compare_location_choices=compare_location_choices,
        complete_compare_two_locations=complete_compare_two_locations,
        main_menu=main_menu,
        build_scenario_location_choice_keyboard=build_scenario_location_choice_keyboard,
    ):
        return

    if handle_geo_text(
        message,
        user_id,
        state,
        WAITING_GEO_LOCATION=WAITING_GEO_LOCATION,
        bot=bot,
        user_states=user_states,
        compare_drafts=compare_drafts,
        details_location_choices=details_location_choices,
        forecast_location_choices=forecast_location_choices,
        compare_location_choices=compare_location_choices,
        main_menu=main_menu,
        geo_request_menu=geo_request_menu,
    ):
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
