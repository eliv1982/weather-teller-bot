from telebot import types

from forecast_service import is_remaining_day_forecast
from handlers.states import (
    WAITING_FORECAST_CITY,
    WAITING_TODAY_FORECAST_CITY,
    WAITING_TOMORROW_FORECAST_CITY,
)


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
    show_days_message=show_forecast_days_message,
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
    show_days_message(message, user_id, ctx=ctx, session_store=session_store)
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
    remaining_day_detector=is_remaining_day_forecast,
) -> bool:
    """Получает 5-дневный прогноз и сразу показывает сегодняшний локальный день."""

    def _formatter(city_label: str, day_key: str, day_items: list[dict]) -> str:
        return ctx.format_today_forecast_response(
            city_label,
            day_key,
            day_items,
            is_remaining_day=remaining_day_detector(day_items),
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
