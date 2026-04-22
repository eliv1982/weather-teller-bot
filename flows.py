import time
from telebot import types

from handlers.states import (
    ALERTS_MENU,
    LOCATIONS_MENU,
    WAITING_COMPARE_CITY_1,
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_DETAILS_CITY,
    WAITING_DETAILS_USE_SAVED_LOCATION,
    WAITING_FORECAST_CITY,
    WAITING_FORECAST_USE_SAVED_LOCATION,
    WAITING_GEO_LOCATION,
)


def start_alerts_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает раздел уведомлений."""
    user_id = message.from_user.id
    ctx.logger.info("Пользователь %s вошёл в раздел уведомлений.", user_id)
    user_data = ctx.load_user(user_id)
    lat = user_data.get("lat")
    lon = user_data.get("lon")

    if lat is None or lon is None:
        ctx.bot.send_message(
            message.chat.id,
            "Сначала нужно сохранить локацию. Используй «Текущая погода» или «Моя геолокация».",
            reply_markup=ctx.main_menu(),
        )
        return

    session_store.set_state(user_id, ALERTS_MENU)
    ctx.bot.send_message(message.chat.id, ctx.format_alerts_status(user_data), reply_markup=ctx.alerts_menu())


def start_locations_flow(message: types.Message, *, ctx, session_store) -> None:
    """Открывает раздел управления сохранёнными локациями."""
    user_id = message.from_user.id
    ctx.logger.info("Пользователь %s вошёл в раздел сохранённых локаций.", user_id)
    session_store.clear_saved_location_flows(user_id)
    session_store.set_state(user_id, LOCATIONS_MENU)
    ctx.bot.send_message(
        message.chat.id,
        "Раздел сохранённых локаций.\nВыбери действие:",
        reply_markup=ctx.locations_menu(),
    )


def start_current_weather_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий ввода населённого пункта для текущей погоды."""
    user_id = message.from_user.id
    session_store.current_location_choices.pop(user_id, None)
    session_store.set_state(user_id, WAITING_CURRENT_WEATHER_CITY)
    ctx.bot.send_message(message.chat.id, "Введи название населённого пункта.")


def start_geo_weather_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий получения погоды по геолокации."""
    ctx.logger.info("Запущен сценарий геолокации для пользователя %s.", message.from_user.id)
    session_store.set_state(message.from_user.id, WAITING_GEO_LOCATION)
    ctx.bot.send_message(
        message.chat.id,
        "Отправь геолокацию через кнопку ниже.\n"
        "Если ты в Telegram Desktop и отправка недоступна, открой бота на телефоне или вернись в меню.",
        reply_markup=ctx.geo_request_menu(),
    )


def start_details_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий получения расширенных данных по населённому пункту."""
    user_id = message.from_user.id
    ctx.logger.info("Запущен сценарий расширенных данных для пользователя %s.", user_id)
    session_store.details_location_choices.pop(user_id, None)

    user_data = ctx.load_user(user_id)
    saved_city = user_data.get("city")
    saved_lat = user_data.get("lat")
    saved_lon = user_data.get("lon")

    if saved_lat is not None and saved_lon is not None:
        ctx.logger.info(
            "Найдена сохранённая локация для /details у пользователя %s: %s (%s, %s).",
            user_id,
            saved_city,
            saved_lat,
            saved_lon,
        )
        session_store.details_saved_drafts[user_id] = {
            "city": saved_city or "Сохранённая локация",
            "lat": saved_lat,
            "lon": saved_lon,
        }
        session_store.user_states[user_id] = WAITING_DETAILS_USE_SAVED_LOCATION
        ctx.bot.send_message(
            message.chat.id,
            f"Использовать последнюю сохранённую локацию: {saved_city or 'Сохранённая локация'}?\n"
            "Ответь: Да или Нет.",
        )
        return

    session_store.user_states[user_id] = WAITING_DETAILS_CITY
    ctx.bot.send_message(message.chat.id, "Введи название населённого пункта для расширенных данных.")


def start_compare_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий сравнения двух населённых пунктов."""
    user_id = message.from_user.id
    ctx.logger.info("Запущен сценарий сравнения населённых пунктов для пользователя %s.", user_id)
    session_store.compare_drafts.pop(user_id, None)
    session_store.compare_location_choices.pop(user_id, None)
    session_store.user_states[user_id] = WAITING_COMPARE_CITY_1
    ctx.bot.send_message(message.chat.id, "Введи первый населённый пункт для сравнения.")


def start_forecast_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий прогноза на 5 дней."""
    user_id = message.from_user.id
    ctx.logger.info("Запущен сценарий прогноза на 5 дней для пользователя %s.", user_id)
    session_store.forecast_location_choices.pop(user_id, None)

    user_data = ctx.load_user(user_id)
    saved_city = user_data.get("city")
    saved_lat = user_data.get("lat")
    saved_lon = user_data.get("lon")

    if saved_lat is not None and saved_lon is not None:
        session_store.forecast_saved_drafts[user_id] = {
            "city": saved_city or "Сохранённая локация",
            "lat": saved_lat,
            "lon": saved_lon,
        }
        session_store.user_states[user_id] = WAITING_FORECAST_USE_SAVED_LOCATION
        ctx.bot.send_message(
            message.chat.id,
            f"Использовать последнюю сохранённую локацию: {saved_city or 'Сохранённая локация'}?\n"
            "Ответь: Да или Нет.",
        )
        return

    session_store.user_states[user_id] = WAITING_FORECAST_CITY
    ctx.bot.send_message(message.chat.id, "Введи название населённого пункта для прогноза на 5 дней.")


def show_forecast_days_message(message: types.Message, user_id: int, *, ctx, session_store) -> None:
    """Показывает сообщение со списком дней прогноза."""
    cache = session_store.forecast_cache.get(user_id)
    if not cache:
        ctx.bot.send_message(
            message.chat.id,
            "Не удалось получить прогноз. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return

    days = list(cache["grouped"].keys())
    keyboard = ctx.build_forecast_days_keyboard(days)
    ctx.bot.send_message(
        message.chat.id,
        f"Выбери день прогноза для {cache['city']}:",
        reply_markup=keyboard,
    )


def send_details_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    preferred_city_label: str | None = None,
    ctx,
    session_store,
) -> bool:
    """Получает и отправляет расширенные данные по известным координатам."""
    weather = ctx.get_current_weather(lat, lon)
    air_components = ctx.get_air_pollution(lat, lon)

    if not weather:
        ctx.logger.warning(
            "Не удалось получить расширенные данные для пользователя %s (населённый пункт: %s, lat: %s, lon: %s).",
            user_id,
            city_fallback,
            lat,
            lon,
        )
        session_store.user_states.pop(user_id, None)
        session_store.details_saved_drafts.pop(user_id, None)
        session_store.details_location_choices.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Не удалось получить расширенные данные. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return False

    # Приоритет у подписи, которую пользователь уже выбрал/сохранил вручную.
    if preferred_city_label:
        city_label = preferred_city_label
    elif city_fallback:
        city_label = city_fallback
    else:
        location = ctx.get_location_by_coordinates(lat, lon)
        city_label = ctx.build_location_label(location, show_coords=False) if location else "Выбранная локация"

    user_data = ctx.load_user(user_id)
    user_data["city"] = city_label
    user_data["lat"] = lat
    user_data["lon"] = lon
    ctx.save_user(user_id, user_data)

    answer = ctx.format_details_response(city_label, weather, air_components)
    session_store.user_states.pop(user_id, None)
    session_store.details_saved_drafts.pop(user_id, None)
    session_store.details_location_choices.pop(user_id, None)
    ctx.bot.send_message(message.chat.id, answer, reply_markup=ctx.main_menu())
    return True


def send_forecast_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    save_location: bool,
    preferred_city_label: str | None = None,
    ctx,
    session_store,
) -> bool:
    """Получает прогноз, сохраняет данные в кэш и показывает дни."""
    forecast_items = ctx.get_forecast_5d3h(lat, lon)
    if not forecast_items:
        ctx.logger.warning(
            "Не удалось получить прогноз для пользователя %s (населённый пункт: %s, lat: %s, lon: %s).",
            user_id,
            city_fallback,
            lat,
            lon,
        )
        session_store.user_states.pop(user_id, None)
        session_store.forecast_saved_drafts.pop(user_id, None)
        session_store.forecast_cache.pop(user_id, None)
        session_store.forecast_location_choices.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Не удалось получить прогноз. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return False

    # Приоритет у подписи, которую пользователь уже выбрал/сохранил вручную.
    if preferred_city_label:
        city_label = preferred_city_label
    elif city_fallback:
        city_label = city_fallback
    else:
        location = ctx.get_location_by_coordinates(lat, lon)
        city_label = ctx.build_location_label(location, show_coords=False) if location else "Выбранная локация"
    grouped = ctx.group_forecast_by_day(forecast_items)
    if not grouped:
        ctx.logger.warning("Прогноз пришёл пустым после группировки для пользователя %s.", user_id)
        session_store.user_states.pop(user_id, None)
        session_store.forecast_saved_drafts.pop(user_id, None)
        session_store.forecast_cache.pop(user_id, None)
        session_store.forecast_location_choices.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Не удалось получить прогноз. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return False

    if save_location:
        user_data = ctx.load_user(user_id)
        user_data["city"] = city_label
        user_data["lat"] = lat
        user_data["lon"] = lon
        ctx.save_user(user_id, user_data)

    session_store.forecast_cache[user_id] = {"city": city_label, "grouped": grouped}
    session_store.user_states.pop(user_id, None)
    session_store.forecast_saved_drafts.pop(user_id, None)
    session_store.forecast_location_choices.pop(user_id, None)
    show_forecast_days_message(message, user_id, ctx=ctx, session_store=session_store)
    return True


def complete_compare_two_locations(
    chat_id: int,
    user_id: int,
    lat_1: float,
    lon_1: float,
    city_label_1: str,
    lat_2: float,
    lon_2: float,
    city_label_2: str,
    *,
    ctx,
    session_store,
) -> None:
    """Загружает погоду по двум точкам и отправляет текст сравнения."""
    weather_1 = ctx.get_current_weather(lat_1, lon_1)
    weather_2 = ctx.get_current_weather(lat_2, lon_2)

    if not weather_1 or not weather_2:
        ctx.logger.warning("Не удалось получить данные для сравнения у пользователя %s.", user_id)
        session_store.user_states.pop(user_id, None)
        session_store.compare_drafts.pop(user_id, None)
        session_store.compare_location_choices.pop(user_id, None)
        ctx.bot.send_message(
            chat_id,
            "Не удалось получить данные для сравнения. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return

    answer = ctx.format_compare_response(city_label_1, weather_1, city_label_2, weather_2)
    ctx.logger.info(
        "Успешно выполнено сравнение для пользователя %s: %s vs %s.",
        user_id,
        city_label_1,
        city_label_2,
    )
    session_store.user_states.pop(user_id, None)
    session_store.compare_drafts.pop(user_id, None)
    session_store.compare_location_choices.pop(user_id, None)
    ctx.bot.send_message(chat_id, answer, reply_markup=ctx.main_menu())


def alerts_worker(*, ctx) -> None:
    """Фоновая проверка прогноза для уведомлений."""
    ctx.logger.info("Фоновый поток уведомлений запущен.")

    while True:
        try:
            all_users = ctx.load_all_users()
            changed = False
            now_ts = int(time.time())

            for user_id_str, user_data in all_users.items():
                if not isinstance(user_data, dict):
                    continue

                user_data = ctx.ensure_notifications_defaults(user_data)
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

                forecast_items = ctx.get_forecast_5d3h(lat, lon)
                if not forecast_items:
                    ctx.logger.warning("Не удалось получить прогноз в фоновом потоке для пользователя %s.", user_id_str)
                    notifications["last_check_ts"] = now_ts
                    changed = True
                    continue

                alerts = ctx.detect_weather_alerts(forecast_items)
                if alerts:
                    city = user_data.get("city") or "неизвестная локация"
                    alert_text = (
                        "🌤 Weather Teller\n"
                        f"Для локации {city} найдено изменение погоды:\n"
                        f"• {alerts[0]}\n"
                        "Проверь прогноз в боте."
                    )
                    try:
                        ctx.bot.send_message(int(user_id_str), alert_text)
                        ctx.logger.info("Уведомление успешно отправлено пользователю %s.", user_id_str)
                    except Exception:
                        ctx.logger.warning("Не удалось отправить уведомление пользователю %s.", user_id_str)

                notifications["last_check_ts"] = now_ts
                changed = True

            if changed:
                ctx.save_all_users(all_users)
        except Exception:
            ctx.logger.exception("Ошибка в фоновом потоке уведомлений.")

        time.sleep(60)
