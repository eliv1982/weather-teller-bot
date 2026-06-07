from datetime import date

from telebot import types

from formatters import format_history_monthly_climate_response
from handlers.callbacks_common import try_delete_message
from handlers.states import (
    WAITING_HISTORY_CLIMATE_MODE,
    WAITING_HISTORY_DATE_PICK,
    WAITING_HISTORY_SECTION,
)
from weather_history_service import get_weather_history_by_date
from weather_monthly_service import get_monthly_climate_normals, get_monthly_history_for_month


def _clear_history_runtime(session_store, user_id: int) -> None:
    session_store.history_drafts.pop(user_id, None)
    session_store.clear_state(user_id)


def _history_restart_reply_markup(ctx):
    main_menu = getattr(ctx, "main_menu", None)
    return main_menu() if callable(main_menu) else None


def start_weather_history_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий архивной погоды и показывает первое подменю раздела."""
    user_id = message.from_user.id
    ctx.logger.info("Запущен сценарий архивной погоды для пользователя %s.", user_id)
    session_store.history_location_choices.pop(user_id, None)
    session_store.history_drafts.pop(user_id, None)
    session_store.user_states[user_id] = WAITING_HISTORY_SECTION
    keyboard_builder = getattr(ctx, "build_history_section_keyboard", None)
    ctx.bot.send_message(
        message.chat.id,
        "Что посмотрим?",
        reply_markup=keyboard_builder() if callable(keyboard_builder) else None,
    )


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
    city_label = preferred_city_label or city_fallback or "Выбранная локация"
    previous_draft = session_store.history_drafts.get(user_id)
    history_section = "daily"
    if isinstance(previous_draft, dict) and str(previous_draft.get("history_section") or "") == "climate":
        history_section = "climate"
    session_store.history_location_choices.pop(user_id, None)
    session_store.history_drafts[user_id] = {
        "history_section": history_section,
        "city_label": city_label,
        "lat": float(lat),
        "lon": float(lon),
    }
    ctx.bot.send_message(
        message.chat.id,
        f"✅ Локация выбрана: {city_label}",
        reply_markup=types.ReplyKeyboardRemove(),
    )
    if history_section == "climate":
        session_store.user_states[user_id] = WAITING_HISTORY_CLIMATE_MODE
        keyboard_builder = getattr(ctx, "build_history_climate_mode_keyboard", None)
        ctx.bot.send_message(
            message.chat.id,
            f"Выбери режим климатической справки по {city_label}:",
            reply_markup=keyboard_builder() if callable(keyboard_builder) else None,
        )
        return True
    session_store.user_states[user_id] = WAITING_HISTORY_DATE_PICK
    date_keyboard_builder = getattr(ctx, "build_history_date_keyboard", None)
    ctx.bot.send_message(
        message.chat.id,
        f"Выбери дату для архивной справки по {city_label}:",
        reply_markup=date_keyboard_builder() if callable(date_keyboard_builder) else None,
    )
    return True


def send_weather_history_by_date(
    message: types.Message,
    user_id: int,
    target_date: date,
    *,
    send_confirmation: bool = True,
    ctx,
    session_store,
    history_getter=get_weather_history_by_date,
    delete_message=try_delete_message,
) -> bool:
    """Получает архивную погоду за выбранную дату и отправляет итоговую сводку."""
    draft = session_store.history_drafts.get(user_id)
    if not isinstance(draft, dict):
        _clear_history_runtime(session_store, user_id)
        ctx.bot.send_message(
            message.chat.id,
            "Начни историю погоды заново.",
            reply_markup=_history_restart_reply_markup(ctx),
        )
        return False

    city_label = str(draft.get("city_label") or "Выбранная локация")
    lat = draft.get("lat")
    lon = draft.get("lon")
    date_prompt_msg_id = draft.get("date_prompt_message_id")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        session_store.history_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Данные локации устарели. Начни историю погоды заново.",
            reply_markup=ctx.main_menu(),
        )
        return False

    result = history_getter(float(lat), float(lon), city_label, target_date)
    delete_message(ctx, message.chat.id, date_prompt_msg_id)
    session_store.history_drafts.pop(user_id, None)
    session_store.user_states.pop(user_id, None)

    if not result.get("ok"):
        ctx.bot.send_message(
            message.chat.id,
            str(result.get("error_message") or "Не удалось получить архивную погоду за эту дату."),
            reply_markup=ctx.main_menu(),
        )
        return False

    short_summary = None
    ai_service = getattr(ctx, "ai_weather_service", None)
    if ai_service is not None and hasattr(ai_service, "explain_history_weather"):
        try:
            short_summary = str(ai_service.explain_history_weather(city_label, result["history"]) or "").strip() or None
        except Exception as exc:
            logger = getattr(ctx, "logger", None)
            if logger is not None:
                logger.warning(
                    "Не удалось получить AI-пояснение архивной погоды для пользователя %s: %s",
                    user_id,
                    exc,
                )

    if send_confirmation:
        ctx.bot.send_message(
            message.chat.id,
            f"✅ Дата введена: {target_date.strftime('%d.%m.%Y')}",
        )
    ctx.bot.send_message(
        message.chat.id,
        ctx.format_history_weather_response(
            city_label,
            result["history"],
            short_summary=short_summary,
        ),
        reply_markup=ctx.main_menu(),
    )
    return True


def send_history_monthly_report(
    message: types.Message,
    user_id: int,
    *,
    send_year_confirmation: bool = True,
    ctx,
    session_store,
    monthly_history_getter=get_monthly_history_for_month,
    monthly_normals_getter=get_monthly_climate_normals,
    delete_message=try_delete_message,
    monthly_formatter_default=format_history_monthly_climate_response,
) -> bool:
    """Получает месячную архивную или климатическую справку и отправляет итоговую сводку."""
    draft = session_store.history_drafts.get(user_id)
    if not isinstance(draft, dict):
        _clear_history_runtime(session_store, user_id)
        ctx.bot.send_message(
            message.chat.id,
            "Начни историю погоды заново.",
            reply_markup=_history_restart_reply_markup(ctx),
        )
        return False

    city_label = str(draft.get("city_label") or "Выбранная локация")
    lat = draft.get("lat")
    lon = draft.get("lon")
    mode = str(draft.get("monthly_mode") or "")
    month = draft.get("monthly_month")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        session_store.history_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Данные локации устарели. Начни историю погоды заново.",
            reply_markup=ctx.main_menu(),
        )
        return False
    if not isinstance(month, int):
        ctx.bot.send_message(
            message.chat.id,
            "Сначала выбери месяц кнопкой ниже.",
        )
        return False

    if mode == "monthly_year":
        year = draft.get("monthly_year")
        if not isinstance(year, int):
            ctx.bot.send_message(
                message.chat.id,
                "Введи год, например 2020.",
            )
            return False
        prompt_msg_id = draft.get("prompt_message_id")
        result = monthly_history_getter(float(lat), float(lon), city_label, year, month)
    elif mode == "monthly_normals":
        year = None
        prompt_msg_id = None
        wait_msg = ctx.bot.send_message(
            message.chat.id,
            "Считаю среднемесячные показатели по архивным данным, это может занять несколько секунд.",
        )
        wait_msg_id = getattr(wait_msg, "message_id", None)
        result = monthly_normals_getter(float(lat), float(lon), city_label, month)
        delete_message(ctx, message.chat.id, wait_msg_id)
    else:
        ctx.bot.send_message(
            message.chat.id,
            "Не удалось определить режим климатической справки. Начни историю погоды заново.",
            reply_markup=ctx.main_menu(),
        )
        session_store.history_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        return False

    session_store.history_drafts.pop(user_id, None)
    session_store.user_states.pop(user_id, None)

    if mode == "monthly_year" and prompt_msg_id:
        delete_message(ctx, message.chat.id, prompt_msg_id)

    if not result.get("ok"):
        ctx.bot.send_message(
            message.chat.id,
            str(result.get("error_message") or "Не удалось получить климатическую справку за выбранный месяц."),
            reply_markup=ctx.main_menu(),
        )
        return False

    report = result["report"]
    short_summary = None
    ai_service = getattr(ctx, "ai_weather_service", None)
    if ai_service is not None and hasattr(ai_service, "explain_monthly_climate"):
        try:
            short_summary = str(ai_service.explain_monthly_climate(city_label, report) or "").strip() or None
        except Exception as exc:
            logger = getattr(ctx, "logger", None)
            if logger is not None:
                logger.warning(
                    "Не удалось получить AI-пояснение месячной климатической справки для пользователя %s: %s",
                    user_id,
                    exc,
                )

    if mode == "monthly_year" and send_year_confirmation and isinstance(year, int):
        ctx.bot.send_message(
            message.chat.id,
            f"✅ Год выбран: {year}",
        )
    formatter = getattr(ctx, "format_history_monthly_climate_response", monthly_formatter_default)
    ctx.bot.send_message(
        message.chat.id,
        formatter(
            city_label,
            report,
            short_summary=short_summary,
        ),
        reply_markup=ctx.main_menu(),
    )
    return True
