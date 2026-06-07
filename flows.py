import time
from datetime import date
from telebot import types
from forecast_service import is_remaining_day_forecast
from formatters import format_history_monthly_climate_response
from flows_history import (
    prepare_weather_history_by_coordinates as run_prepare_weather_history_by_coordinates,
    send_history_monthly_report as run_send_history_monthly_report,
    send_weather_history_by_date as run_send_weather_history_by_date,
    start_weather_history_flow as run_start_weather_history_flow,
)

from handlers.callbacks_common import try_delete_message
from handlers.states import (
    ALERTS_MENU,
    LOCATIONS_MENU,
    SOURCE_COMPARE_MENU,
    WEATHER_MENU,
    WAITING_ALERTS_SUBSCRIPTION_MENU,
    WAITING_COMPARE_CITY_1,
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_DETAILS_CITY,
    WAITING_FORECAST_CITY,
    WAITING_GEO_LOCATION,
    WAITING_HISTORY_CITY,
    WAITING_SOURCE_COMPARE_CITY,
    WAITING_SOURCE_COMPARE_DATE_PICK,
    WAITING_TODAY_FORECAST_CITY,
    WAITING_TOMORROW_FORECAST_CITY,
)
from source_compare_service import (
    compare_current_sources,
    compare_sources_by_date,
    compare_today_sources,
    compare_tomorrow_sources,
    get_source_compare_available_dates,
)
from weather_history_service import get_weather_history_by_date
from weather_monthly_service import get_monthly_climate_normals, get_monthly_history_for_month
from workers.alerts_worker import alerts_worker as run_alerts_worker


def _get_favorite_location(user_data: dict) -> dict | None:
    """Возвращает основную локацию пользователя из saved_locations, если она валидна."""
    favorite_id = user_data.get("favorite_location_id")
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(favorite_id, str) or not favorite_id:
        return None
    if not isinstance(saved_locations, list):
        return None

    favorite_item = next(
        (
            item
            for item in saved_locations
            if isinstance(item, dict) and item.get("id") == favorite_id
        ),
        None,
    )
    if not isinstance(favorite_item, dict):
        return None
    if favorite_item.get("lat") is None or favorite_item.get("lon") is None:
        return None
    return favorite_item


def start_alerts_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает раздел уведомлений."""
    user_id = message.from_user.id
    ctx.logger.info("Пользователь %s вошёл в раздел уведомлений.", user_id)
    ctx.alerts_subscription_service.ensure_defaults(ctx.ensure_notifications_defaults(ctx.load_user(user_id)))
    session_store.set_state(user_id, WAITING_ALERTS_SUBSCRIPTION_MENU)
    ctx.bot.send_message(
        message.chat.id,
        "Раздел уведомлений по нескольким локациям.\nВыбери действие:",
        reply_markup=ctx.alerts_menu(),
    )


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
    session_store.current_favorite_drafts.pop(user_id, None)
    user_data = ctx.load_user(user_id)
    has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))
    session_store.set_state(user_id, WAITING_CURRENT_WEATHER_CITY)
    ctx.bot.send_message(
        message.chat.id,
        "Введи название населённого пункта или выбери другой способ ниже:",
        reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
    )


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
    session_store.details_favorite_drafts.pop(user_id, None)
    user_data = ctx.load_user(user_id)
    has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))

    session_store.user_states[user_id] = WAITING_DETAILS_CITY
    ctx.bot.send_message(
        message.chat.id,
        "Введи название населённого пункта или выбери другой способ ниже:",
        reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
    )


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
    session_store.forecast_favorite_drafts.pop(user_id, None)
    user_data = ctx.load_user(user_id)
    has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))

    session_store.user_states[user_id] = WAITING_FORECAST_CITY
    ctx.bot.send_message(
        message.chat.id,
        "Введи название населенного пункта или выбери другой способ ниже:",
        reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
    )


def start_tomorrow_forecast_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий прогноза на завтра."""
    user_id = message.from_user.id
    ctx.logger.info("Запущен сценарий прогноза на завтра для пользователя %s.", user_id)
    session_store.forecast_location_choices.pop(user_id, None)
    session_store.forecast_favorite_drafts.pop(user_id, None)
    user_data = ctx.load_user(user_id)
    has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))

    session_store.user_states[user_id] = WAITING_TOMORROW_FORECAST_CITY
    ctx.bot.send_message(
        message.chat.id,
        "Введи название населенного пункта или выбери другой способ ниже:",
        reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
    )


def start_today_forecast_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий прогноза на сегодня."""
    user_id = message.from_user.id
    ctx.logger.info("Запущен сценарий прогноза на сегодня для пользователя %s.", user_id)
    session_store.forecast_location_choices.pop(user_id, None)
    session_store.forecast_favorite_drafts.pop(user_id, None)
    user_data = ctx.load_user(user_id)
    has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))

    session_store.user_states[user_id] = WAITING_TODAY_FORECAST_CITY
    ctx.bot.send_message(
        message.chat.id,
        "Введи название населённого пункта или выбери другой способ ниже:",
        reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
    )


def start_source_compare_flow(message: types.Message, *, ctx, session_store) -> None:
    """Открывает подменю выбора режима сравнения источников."""
    user_id = message.from_user.id
    ctx.logger.info("Запущен сценарий сверки источников для пользователя %s.", user_id)
    session_store.source_compare_location_choices.pop(user_id, None)
    session_store.source_compare_drafts.pop(user_id, None)
    session_store.user_states[user_id] = SOURCE_COMPARE_MENU
    ctx.bot.send_message(
        message.chat.id,
        "Выбери режим сравнения источников.",
        reply_markup=ctx.source_compare_mode_menu(),
    )


def start_source_compare_mode_flow(message: types.Message, mode: str, *, ctx, session_store) -> None:
    """Запускает конкретный режим source compare и переводит к выбору локации."""
    user_id = message.from_user.id
    session_store.source_compare_location_choices.pop(user_id, None)
    session_store.source_compare_drafts[user_id] = {"mode": mode}
    user_data = ctx.load_user(user_id)
    has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))
    session_store.user_states[user_id] = WAITING_SOURCE_COMPARE_CITY
    ctx.bot.send_message(
        message.chat.id,
        "Введи название населённого пункта или выбери другой способ ниже:",
        reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
    )


def start_weather_history_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий архивной погоды и показывает первое подменю раздела."""
    run_start_weather_history_flow(message, ctx=ctx, session_store=session_store)


def start_weather_menu_flow(message: types.Message, *, ctx, session_store) -> None:
    """Открывает экран выбора погодного раздела и сохраняет menu-state."""
    session_store.set_state(message.from_user.id, WEATHER_MENU)
    ctx.bot.send_message(
        message.chat.id,
        "Выбери раздел в меню ниже.",
        reply_markup=ctx.weather_menu(),
    )


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
    # Снимаем сценарную reply-клавиатуру выбора локации, оставляя inline-навигацию прогноза.
    ctx.bot.send_message(
        message.chat.id,
        "Прогноз готов.",
        reply_markup=types.ReplyKeyboardRemove(),
    )
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
    snapshot_id = session_store.generate_ai_snapshot_id(user_id)
    session_store.ai_details_snapshots[snapshot_id] = {
        "user_id": user_id,
        "city_label": city_label,
        "weather": weather,
        "air_components": air_components,
        "created_at": time.time(),
    }
    session_store.cleanup_ai_snapshots()
    ctx.bot.send_message(message.chat.id, answer, reply_markup=ctx.main_menu())
    ctx.bot.send_message(
        message.chat.id,
        "💡 Хочешь простое пояснение данных?",
        reply_markup=ctx.build_ai_action_keyboard(
            "💡 Пояснить данные",
            f"ai_details_explain:{snapshot_id}",
        ),
    )
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


def _send_direct_day_forecast_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    save_location: bool,
    preferred_city_label: str | None,
    day_getter,
    formatter,
    ready_message: str,
    missing_message: str,
    ai_callback_prefix: str,
    ai_prompt_message: str,
    ctx,
    session_store,
) -> bool:
    """Получает 5-дневный прогноз и сразу показывает выбранный локальный день."""
    forecast_items = ctx.get_forecast_5d3h(lat, lon)
    if not forecast_items:
        ctx.logger.warning(
            "Не удалось получить прямой дневной прогноз для пользователя %s (населённый пункт: %s, lat: %s, lon: %s).",
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

    if preferred_city_label:
        city_label = preferred_city_label
    elif city_fallback:
        city_label = city_fallback
    else:
        location = ctx.get_location_by_coordinates(lat, lon)
        city_label = ctx.build_location_label(location, show_coords=False) if location else "Выбранная локация"

    grouped = ctx.group_forecast_by_day(forecast_items)
    day_pair = day_getter(grouped)
    if day_pair is None:
        ctx.logger.warning("Нужный день прогноза не найден в ответе сервиса для пользователя %s.", user_id)
        session_store.user_states.pop(user_id, None)
        session_store.forecast_saved_drafts.pop(user_id, None)
        session_store.forecast_cache.pop(user_id, None)
        session_store.forecast_location_choices.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            missing_message,
            reply_markup=ctx.main_menu(),
        )
        return False

    if save_location:
        user_data = ctx.load_user(user_id)
        user_data["city"] = city_label
        user_data["lat"] = lat
        user_data["lon"] = lon
        ctx.save_user(user_id, user_data)

    day_key, day_items = day_pair
    session_store.forecast_cache[user_id] = {"city": city_label, "grouped": grouped}
    session_store.user_states.pop(user_id, None)
    session_store.forecast_saved_drafts.pop(user_id, None)
    session_store.forecast_location_choices.pop(user_id, None)

    text = formatter(city_label, day_key, day_items)
    ctx.bot.send_message(message.chat.id, ready_message, reply_markup=types.ReplyKeyboardRemove())
    ctx.bot.send_message(message.chat.id, text, reply_markup=ctx.main_menu())
    ctx.bot.send_message(
        message.chat.id,
        ai_prompt_message,
        reply_markup=ctx.build_ai_action_keyboard(
            "✨ Короткое пояснение прогноза",
            f"{ai_callback_prefix}:{day_key}",
        ),
    )
    return True


def send_tomorrow_forecast_by_coordinates(
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
    """Получает 5-дневный прогноз и сразу показывает день завтрашнего прогноза."""
    return _send_direct_day_forecast_by_coordinates(
        message,
        user_id,
        lat,
        lon,
        city_fallback,
        save_location=save_location,
        preferred_city_label=preferred_city_label,
        day_getter=ctx.get_tomorrow_forecast_day,
        formatter=ctx.format_tomorrow_forecast_response,
        ready_message="Прогноз на завтра готов.",
        missing_message="Не нашла прогноз на завтра в ответе погодного сервиса. Попробуй открыть прогноз на 5 дней.",
        ai_callback_prefix="ai_tomorrow_forecast_day",
        ai_prompt_message="✨ Хочешь короткое пояснение прогноза?",
        ctx=ctx,
        session_store=session_store,
    )


def send_today_forecast_by_coordinates(
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
    """Получает 5-дневный прогноз и сразу показывает сегодняшний локальный день."""
    def _formatter(city_label: str, day_key: str, day_items: list[dict]) -> str:
        return ctx.format_today_forecast_response(
            city_label,
            day_key,
            day_items,
            is_remaining_day=is_remaining_day_forecast(day_items),
        )

    return _send_direct_day_forecast_by_coordinates(
        message,
        user_id,
        lat,
        lon,
        city_fallback,
        save_location=save_location,
        preferred_city_label=preferred_city_label,
        day_getter=ctx.get_today_forecast_day,
        formatter=_formatter,
        ready_message="Прогноз на сегодня готов.",
        missing_message="Не нашла прогноз на сегодня в ответе погодного сервиса. Попробуй открыть прогноз на 5 дней.",
        ai_callback_prefix="ai_today_forecast_day",
        ai_prompt_message="✨ Хочешь короткое пояснение прогноза?",
        ctx=ctx,
        session_store=session_store,
    )


def send_source_compare_by_coordinates(
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
    """Сравнивает OpenWeather и Open-Meteo для выбранного режима source compare."""
    city_label = preferred_city_label or city_fallback or "Выбранная локация"
    draft = session_store.source_compare_drafts.get(user_id)
    mode = str(draft.get("mode") or "tomorrow") if isinstance(draft, dict) else "tomorrow"
    if mode == "current":
        result = compare_current_sources(lat, lon, city_label)
    elif mode == "today":
        result = compare_today_sources(lat, lon, city_label)
    elif mode == "date":
        result = get_source_compare_available_dates(lat, lon, city_label)
    else:
        result = compare_tomorrow_sources(lat, lon, city_label)

    if not result.get("ok"):
        session_store.user_states.pop(user_id, None)
        session_store.source_compare_location_choices.pop(user_id, None)
        session_store.source_compare_drafts.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            str(result.get("error_message") or "Не удалось сравнить источники: один из прогнозов сейчас недоступен."),
            reply_markup=ctx.main_menu(),
        )
        return False

    session_store.source_compare_location_choices.pop(user_id, None)

    if mode == "date":
        available_days = result.get("available_days") or []
        if not available_days:
            session_store.user_states.pop(user_id, None)
            session_store.source_compare_drafts.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "Не удалось найти общие даты прогноза по двум источникам.",
                reply_markup=ctx.main_menu(),
            )
            return False
        session_store.source_compare_drafts[user_id] = {
            "mode": mode,
            "city_label": city_label,
            "lat": float(lat),
            "lon": float(lon),
            "available_days": available_days,
            "openweather_grouped": result["openweather_grouped"],
            "open_meteo_grouped": result["open_meteo_grouped"],
        }
        session_store.user_states[user_id] = WAITING_SOURCE_COMPARE_DATE_PICK
        ctx.bot.send_message(message.chat.id, "Сравнение по локации подготовлено.", reply_markup=types.ReplyKeyboardRemove())
        ctx.bot.send_message(
            message.chat.id,
            f"Выбери дату прогноза для {city_label}:",
            reply_markup=ctx.build_source_compare_days_keyboard(available_days),
        )
        return True

    session_store.user_states.pop(user_id, None)
    session_store.source_compare_drafts.pop(user_id, None)
    if mode == "current":
        text = ctx.format_source_compare_current_response(
            city_label,
            result["openweather"],
            result["open_meteo"],
        )
        ready_message = "Сравнение текущей погоды готово."
    else:
        formatter = ctx.format_source_compare_response
        title = str(result.get("title") or "🔎 Сравнение прогнозов")
        try:
            text = formatter(
                city_label,
                result["openweather"],
                result["open_meteo"],
                title=title,
            )
        except TypeError:
            text = formatter(
                city_label,
                result["openweather"],
                result["open_meteo"],
            )
        ready_message = "Сравнение прогнозов готово."
    ctx.bot.send_message(message.chat.id, ready_message, reply_markup=types.ReplyKeyboardRemove())
    ctx.bot.send_message(message.chat.id, text, reply_markup=ctx.main_menu())
    return True


def send_source_compare_by_selected_date(
    message: types.Message,
    user_id: int,
    selected_day: str,
    *,
    ctx,
    session_store,
) -> bool:
    """Сравнивает источники на выбранную дату после шага выбора даты."""
    draft = session_store.source_compare_drafts.get(user_id)
    if not isinstance(draft, dict):
        ctx.bot.send_message(message.chat.id, "Данные устарели. Начни сравнение источников заново.", reply_markup=ctx.main_menu())
        return False
    city_label = str(draft.get("city_label") or "Выбранная локация")
    lat = draft.get("lat")
    lon = draft.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        ctx.bot.send_message(message.chat.id, "Данные локации устарели. Начни сравнение источников заново.", reply_markup=ctx.main_menu())
        session_store.source_compare_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        return False

    result = compare_sources_by_date(float(lat), float(lon), city_label, selected_day)
    session_store.user_states.pop(user_id, None)

    if not result.get("ok"):
        session_store.source_compare_drafts.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            str(result.get("error_message") or "Не удалось сравнить источники на выбранную дату."),
            reply_markup=ctx.main_menu(),
        )
        return False

    formatter = ctx.format_source_compare_response
    title = str(result.get("title") or f"🔎 Сравнение прогнозов на {selected_day}")
    try:
        text = formatter(
            city_label,
            result["openweather"],
            result["open_meteo"],
            title=title,
        )
    except TypeError:
        text = formatter(
            city_label,
            result["openweather"],
            result["open_meteo"],
        )
    draft["selected_day"] = selected_day
    session_store.source_compare_drafts[user_id] = draft
    ctx.bot.send_message(message.chat.id, text, reply_markup=ctx.build_source_compare_date_post_result_keyboard())
    return True


def prepare_weather_history_by_coordinates(
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
    """Сохраняет выбранную локацию и переводит пользователя к нужной ветке истории."""
    return run_prepare_weather_history_by_coordinates(
        message,
        user_id,
        lat,
        lon,
        city_fallback,
        preferred_city_label=preferred_city_label,
        ctx=ctx,
        session_store=session_store,
    )


def send_weather_history_by_date(
    message: types.Message,
    user_id: int,
    target_date: date,
    *,
    send_confirmation: bool = True,
    ctx,
    session_store,
) -> bool:
    """Получает архивную погоду за выбранную дату и отправляет итоговую сводку."""
    return run_send_weather_history_by_date(
        message,
        user_id,
        target_date,
        send_confirmation=send_confirmation,
        ctx=ctx,
        session_store=session_store,
        history_getter=get_weather_history_by_date,
        delete_message=try_delete_message,
    )


def send_history_monthly_report(
    message: types.Message,
    user_id: int,
    *,
    send_year_confirmation: bool = True,
    ctx,
    session_store,
) -> bool:
    """Получает месячную архивную или климатическую справку и отправляет итоговую сводку."""
    return run_send_history_monthly_report(
        message,
        user_id,
        send_year_confirmation=send_year_confirmation,
        ctx=ctx,
        session_store=session_store,
        monthly_history_getter=get_monthly_history_for_month,
        monthly_normals_getter=get_monthly_climate_normals,
        delete_message=try_delete_message,
        monthly_formatter_default=format_history_monthly_climate_response,
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
    run_alerts_worker(ctx=ctx)
