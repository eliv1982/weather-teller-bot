from telebot import types

from handlers.states import SOURCE_COMPARE_MENU, WAITING_SOURCE_COMPARE_CITY, WAITING_SOURCE_COMPARE_DATE_PICK
from source_compare_service import (
    compare_current_sources,
    compare_sources_by_date,
    compare_today_sources,
    compare_tomorrow_sources,
    get_source_compare_available_dates,
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
    current_sources_comparer=compare_current_sources,
    today_sources_comparer=compare_today_sources,
    tomorrow_sources_comparer=compare_tomorrow_sources,
    available_dates_getter=get_source_compare_available_dates,
) -> bool:
    """Сравнивает OpenWeather и Open-Meteo для выбранного режима source compare."""
    city_label = preferred_city_label or city_fallback or "Выбранная локация"
    draft = session_store.source_compare_drafts.get(user_id)
    mode = str(draft.get("mode") or "tomorrow") if isinstance(draft, dict) else "tomorrow"
    if mode == "current":
        result = current_sources_comparer(lat, lon, city_label)
    elif mode == "today":
        result = today_sources_comparer(lat, lon, city_label)
    elif mode == "date":
        result = available_dates_getter(lat, lon, city_label)
    else:
        result = tomorrow_sources_comparer(lat, lon, city_label)

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
    sources_by_date_comparer=compare_sources_by_date,
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

    result = sources_by_date_comparer(float(lat), float(lon), city_label, selected_day)
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
