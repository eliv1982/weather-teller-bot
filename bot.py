import os
import logging
import threading
from functools import partial
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
    rank_locations,
    build_location_label,
    get_location_by_coordinates,
)
from keyboards import (
    add_saved_location_menu,
    alerts_add_location_menu,
    alerts_menu,
    build_alert_subscriptions_keyboard,
    build_current_weather_location_keyboard,
    build_favorite_pick_keyboard,
    build_forecast_day_keyboard,
    build_forecast_days_keyboard,
    build_location_pick_keyboard,
    build_saved_locations_keyboard,
    build_scenario_location_choice_keyboard,
    geo_request_menu,
    location_input_menu,
    locations_menu,
    main_menu,
    yes_no_menu,
)
from formatters import (
    format_alerts_status,
    format_alert_subscriptions,
    format_compare_response,
    format_details_response,
    format_saved_locations,
    format_weather_response,
    help_text,
)
from forecast_service import group_forecast_by_day, format_forecast_day
from alerts_subscription_service import AlertsSubscriptionService
from alerts_service import (
    ensure_notifications_defaults,
    detect_weather_alerts,
    migrate_legacy_alert_to_subscriptions,
)
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
from handlers.callbacks_details import handle_details_location_callback as handle_details_callback_logic
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
    WAITING_ALERTS_ADD_GEO,
    WAITING_ALERTS_ADD_MENU,
    WAITING_ALERTS_ADD_PICK,
    WAITING_ALERTS_ADD_COORDS,
    WAITING_ALERTS_ADD_SAVED_PICK,
    WAITING_ALERTS_ADD_TEXT,
    WAITING_ALERTS_DELETE_PICK,
    WAITING_ALERTS_INTERVAL_PICK,
    WAITING_ALERTS_INTERVAL_VALUE,
    WAITING_ALERTS_SUBSCRIPTION_MENU,
    WAITING_ALERTS_TOGGLE_PICK,
    WAITING_COMPARE_CITY_1,
    WAITING_COMPARE_CITY_2,
    WAITING_COMPARE_LOCATION_PICK,
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_CURRENT_WEATHER_COORDS,
    WAITING_DETAILS_CITY,
    WAITING_DETAILS_COORDS,
    WAITING_DETAILS_PICK,
    WAITING_DETAILS_USE_SAVED_LOCATION,
    WAITING_FORECAST_CITY,
    WAITING_FORECAST_COORDS,
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
from postgres_storage import (
    init_postgres_db,
    load_all_users,
    load_user,
    save_all_users,
    save_user,
)
from session_store import SessionStore
from app_context import AppContext
from flows import (
    alerts_worker as flow_alerts_worker,
    complete_compare_two_locations as flow_complete_compare_two_locations,
    send_details_by_coordinates as flow_send_details_by_coordinates,
    send_forecast_by_coordinates as flow_send_forecast_by_coordinates,
    start_alerts_flow as flow_start_alerts_flow,
    start_compare_flow as flow_start_compare_flow,
    start_current_weather_flow as flow_start_current_weather_flow,
    start_details_flow as flow_start_details_flow,
    start_forecast_flow as flow_start_forecast_flow,
    start_geo_weather_flow as flow_start_geo_weather_flow,
    start_locations_flow as flow_start_locations_flow,
)


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
session_store = SessionStore()
alerts_subscription_service = AlertsSubscriptionService()

ctx = AppContext(
    bot=bot,
    logger=logger,
    load_user=load_user,
    save_user=save_user,
    load_all_users=load_all_users,
    save_all_users=save_all_users,
    main_menu=main_menu,
    alerts_menu=alerts_menu,
    alerts_add_location_menu=alerts_add_location_menu,
    locations_menu=locations_menu,
    add_saved_location_menu=add_saved_location_menu,
    location_input_menu=location_input_menu,
    geo_request_menu=geo_request_menu,
    yes_no_menu=yes_no_menu,
    build_current_weather_location_keyboard=build_current_weather_location_keyboard,
    build_forecast_days_keyboard=build_forecast_days_keyboard,
    build_forecast_day_keyboard=build_forecast_day_keyboard,
    build_location_pick_keyboard=build_location_pick_keyboard,
    build_alert_subscriptions_keyboard=build_alert_subscriptions_keyboard,
    build_saved_locations_keyboard=build_saved_locations_keyboard,
    build_scenario_location_choice_keyboard=build_scenario_location_choice_keyboard,
    build_favorite_pick_keyboard=build_favorite_pick_keyboard,
    format_alerts_status=format_alerts_status,
    format_alert_subscriptions=format_alert_subscriptions,
    format_compare_response=format_compare_response,
    format_details_response=format_details_response,
    format_saved_locations=format_saved_locations,
    format_weather_response=format_weather_response,
    help_text=help_text,
    alerts_subscription_service=alerts_subscription_service,
    ensure_notifications_defaults=ensure_notifications_defaults,
    ensure_alert_subscriptions_defaults=alerts_subscription_service.ensure_defaults,
    migrate_legacy_alert_to_subscriptions=migrate_legacy_alert_to_subscriptions,
    add_alert_subscription=alerts_subscription_service.add_subscription,
    detect_weather_alerts=detect_weather_alerts,
    save_saved_location_item=save_saved_location_item,
    complete_current_weather_from_location=complete_current_weather_from_location,
    complete_alerts_location_from_item=complete_alerts_location_from_item,
    group_forecast_by_day=group_forecast_by_day,
    format_forecast_day=format_forecast_day,
    build_geocode_item_with_disambiguated_label=build_geocode_item_with_disambiguated_label,
    rank_locations=rank_locations,
    get_locations=get_locations,
    build_location_label=build_location_label,
    get_location_by_coordinates=get_location_by_coordinates,
    get_current_weather=get_current_weather,
    get_forecast_5d3h=get_forecast_5d3h,
    get_air_pollution=get_air_pollution,
)

start_alerts_flow = partial(flow_start_alerts_flow, ctx=ctx, session_store=session_store)
start_locations_flow = partial(flow_start_locations_flow, ctx=ctx, session_store=session_store)
start_current_weather_flow = partial(flow_start_current_weather_flow, ctx=ctx, session_store=session_store)
start_geo_weather_flow = partial(flow_start_geo_weather_flow, ctx=ctx, session_store=session_store)
start_details_flow = partial(flow_start_details_flow, ctx=ctx, session_store=session_store)
start_compare_flow = partial(flow_start_compare_flow, ctx=ctx, session_store=session_store)
start_forecast_flow = partial(flow_start_forecast_flow, ctx=ctx, session_store=session_store)
send_details_by_coordinates = partial(flow_send_details_by_coordinates, ctx=ctx, session_store=session_store)
send_forecast_by_coordinates = partial(flow_send_forecast_by_coordinates, ctx=ctx, session_store=session_store)
complete_compare_two_locations = partial(flow_complete_compare_two_locations, ctx=ctx, session_store=session_store)
alerts_worker = partial(flow_alerts_worker, ctx=ctx)

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


def _message_stub_for_chat(chat_id: int) -> SimpleNamespace:
    """Заглушка сообщения с chat.id для вызовов send_* из обработчиков callback."""
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id))


@bot.message_handler(commands=["start"])
def handle_start(message: types.Message) -> None:
    """Обрабатывает команду /start."""
    logger.info("Получена команда /start от пользователя %s.", message.from_user.id)
    session_store.clear_all_user_runtime(message.from_user.id)
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
    state = session_store.get_state(user_id)

    if state in {
        WAITING_ALERTS_SUBSCRIPTION_MENU,
        WAITING_ALERTS_ADD_MENU,
        WAITING_ALERTS_ADD_TEXT,
        WAITING_ALERTS_ADD_PICK,
        WAITING_ALERTS_ADD_GEO,
        WAITING_ALERTS_ADD_COORDS,
        WAITING_ALERTS_ADD_SAVED_PICK,
        WAITING_ALERTS_TOGGLE_PICK,
        WAITING_ALERTS_INTERVAL_PICK,
        WAITING_ALERTS_INTERVAL_VALUE,
        WAITING_ALERTS_DELETE_PICK,
    }:
        session_store.alerts_location_choices.pop(user_id, None)
        session_store.alerts_subscription_drafts.pop(user_id, None)
        session_store.user_states[user_id] = ALERTS_MENU
        user_data = alerts_subscription_service.ensure_defaults(ensure_notifications_defaults(load_user(user_id)))
        bot.send_message(
            message.chat.id,
            format_alert_subscriptions(user_data),
            reply_markup=alerts_menu(),
        )
        return

    session_store.clear_all_user_runtime(user_id)
    bot.send_message(message.chat.id, "Главное меню.", reply_markup=main_menu())


@bot.message_handler(content_types=["location"])
def handle_location_message(message: types.Message) -> None:
    """Обрабатывает геолокацию от пользователя."""
    user_id = message.from_user.id
    state = session_store.get_state(user_id)

    if state == WAITING_ALERTS_ADD_GEO:
        session_store.alerts_location_choices.pop(user_id, None)
        location_data = message.location
        lat = location_data.latitude
        lon = location_data.longitude
        logger.info("Получена геолокация для добавления подписки пользователя %s: lat=%s, lon=%s.", user_id, lat, lon)
        location = get_location_by_coordinates(lat, lon)
        if location:
            label = build_location_label(location, show_coords=False)
        else:
            label = "Выбранная геолокация"

        user_data = alerts_subscription_service.ensure_defaults(ensure_notifications_defaults(load_user(user_id)))
        user_data, added = alerts_subscription_service.add_subscription(
            user_data,
            location_id=alerts_subscription_service.build_subscription_id(float(lat), float(lon)),
            title=label,
            label=label,
            lat=float(lat),
            lon=float(lon),
        )
        if added:
            save_user(user_id, user_data)
        session_store.alerts_subscription_drafts.pop(user_id, None)
        session_store.user_states[user_id] = ALERTS_MENU
        bot.send_message(
            message.chat.id,
            "✅ Подписка добавлена." if added else "Такая подписка уже существует.",
            reply_markup=alerts_menu(),
        )
        bot.send_message(
            message.chat.id,
            format_alert_subscriptions(user_data),
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

        session_store.saved_location_drafts[user_id] = {
            "lat": float(lat),
            "lon": float(lon),
            "label": label,
        }
        session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_TITLE
        bot.send_message(
            message.chat.id,
            "Введи название для этой локации, например: Дом",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    session_store.clear_location_choices(user_id)
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
        session_store.user_states.pop(user_id, None)
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
    session_store.user_states.pop(user_id, None)
    bot.send_message(message.chat.id, answer, reply_markup=main_menu())


@bot.callback_query_handler(func=lambda call: call.data.startswith("current_"))
def handle_current_weather_location_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации или отмену в сценарии «Текущая погода»."""
    handle_current_weather_callback(
        call,
        ctx=ctx,
        session_store=session_store,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("alerts_"))
def handle_alerts_location_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации для уведомлений (inline) или отмену."""
    handle_alerts_callback_logic(
        call,
        ctx=ctx,
        session_store=session_store,
        ALERTS_MENU=ALERTS_MENU,
        WAITING_ALERTS_ADD_MENU=WAITING_ALERTS_ADD_MENU,
        WAITING_ALERTS_INTERVAL_VALUE=WAITING_ALERTS_INTERVAL_VALUE,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("details_"))
def handle_details_location_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации для расширенных данных (inline) или отмену."""
    handle_details_callback_logic(
        call,
        ctx=ctx,
        session_store=session_store,
        send_details_by_coordinates=send_details_by_coordinates,
        _message_stub_for_chat=_message_stub_for_chat,
    )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("compare_pick:") or call.data == "compare_cancel"
)
def handle_compare_location_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор населённого пункта при сравнении (inline) или отмену."""
    handle_compare_callback_logic(
        call,
        ctx=ctx,
        session_store=session_store,
        WAITING_COMPARE_CITY_2=WAITING_COMPARE_CITY_2,
        complete_compare_two_locations=complete_compare_two_locations,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("favorite_pick:"))
def handle_favorite_pick_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор основной локации из списка сохранённых."""
    handle_favorite_callback_logic(
        call,
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU=LOCATIONS_MENU,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_location_pick:"))
def handle_delete_location_pick_callback(call: types.CallbackQuery) -> None:
    """Удаляет выбранную сохранённую локацию."""
    handle_delete_location_callback_logic(
        call,
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU=LOCATIONS_MENU,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("rename_location_pick:"))
def handle_rename_location_pick_callback(call: types.CallbackQuery) -> None:
    """Запоминает выбранную локацию и запрашивает новое имя."""
    handle_rename_location_callback_logic(
        call,
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU=LOCATIONS_MENU,
        WAITING_RENAME_LOCATION_TITLE=WAITING_RENAME_LOCATION_TITLE,
        types=types,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("savedloc_"))
def handle_saved_location_pick_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает выбор локации при добавлении новой сохранённой локации."""
    handle_saved_location_callback_logic(
        call,
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU=LOCATIONS_MENU,
        WAITING_NEW_SAVED_LOCATION_TITLE=WAITING_NEW_SAVED_LOCATION_TITLE,
        types=types,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("forecast_"))
def handle_forecast_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает inline-навигацию прогноза и выбор локации перед прогнозом."""
    handle_forecast_callback_logic(
        call,
        ctx=ctx,
        session_store=session_store,
        _message_stub_for_chat=_message_stub_for_chat,
        send_forecast_by_coordinates=send_forecast_by_coordinates,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("yn_"))
def handle_yes_no_callback(call: types.CallbackQuery) -> None:
    """Обрабатывает inline-кнопки Да/Нет/В меню для yes/no-сценариев."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    action = call.data

    if action == "yn_yes":
        text_value = "Да"
    elif action == "yn_no":
        text_value = "Нет"
    else:
        text_value = "⬅️ В меню"

    stub_message = SimpleNamespace(
        text=text_value,
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
    )

    bot.answer_callback_query(call.id)

    if text_value == "⬅️ В меню":
        handle_back_to_menu(stub_message)
        return

    handle_unknown_text(stub_message)


@bot.message_handler(func=lambda message: True)
def handle_unknown_text(message: types.Message) -> None:
    """Маршрутизирует текст в сценарный обработчик по текущему состоянию."""
    user_id = message.from_user.id
    state = session_store.get_state(user_id)

    if state in LOCATIONS_STATES and handle_locations_text(
        message,
        user_id,
        state,
        ctx=ctx,
        session_store=session_store,
    ):
        return

    if state in CURRENT_STATES and handle_current_text(
        message,
        user_id,
        state,
        ctx=ctx,
        session_store=session_store,
    ):
        return

    if state in DETAILS_STATES and handle_details_text(
        message,
        user_id,
        state,
        ctx=ctx,
        session_store=session_store,
        send_details_by_coordinates=send_details_by_coordinates,
    ):
        return

    if state in FORECAST_STATES and handle_forecast_text(
        message,
        user_id,
        state,
        ctx=ctx,
        session_store=session_store,
        send_forecast_by_coordinates=send_forecast_by_coordinates,
    ):
        return

    if state in ALERTS_STATES and handle_alerts_text(
        message,
        user_id,
        state,
        ctx=ctx,
        session_store=session_store,
    ):
        return

    if state in COMPARE_STATES and handle_compare_text(
        message,
        user_id,
        state,
        ctx=ctx,
        session_store=session_store,
        complete_compare_two_locations=complete_compare_two_locations,
    ):
        return

    if handle_geo_text(
        message,
        user_id,
        state,
        WAITING_GEO_LOCATION=WAITING_GEO_LOCATION,
        ctx=ctx,
        session_store=session_store,
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
        try:
            init_postgres_db()
            logger.info("Инициализация PostgreSQL выполнена успешно.")
        except Exception:
            logger.exception("Ошибка инициализации PostgreSQL. Проверь параметры подключения и доступность БД.")
            raise SystemExit(1)

        alerts_thread = threading.Thread(target=alerts_worker, daemon=True)
        alerts_thread.start()
        logger.info("Фоновый поток alerts_worker запущен (PID=%s).", process_id)
        logger.info("Старт polling (PID=%s).", process_id)
        bot.infinity_polling(skip_pending=True)
    except KeyboardInterrupt:
        print("Бот остановлен пользователем.")
