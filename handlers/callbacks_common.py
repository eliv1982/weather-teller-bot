import logging

from .states import (
    WAITING_COMPARE_CITY_1,
    WAITING_COMPARE_CITY_2,
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_DETAILS_CITY,
    WAITING_FORECAST_CITY,
    WAITING_SOURCE_COMPARE_CITY,
    WAITING_TODAY_FORECAST_CITY,
    WAITING_TOMORROW_FORECAST_CITY,
)


logger = logging.getLogger(__name__)


def mark_location_choice_selected(call, ctx, city_label: str) -> None:
    """Best-effort cleanup for an inline location-choice message."""
    message = getattr(call, "message", None)
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    message_id = getattr(message, "message_id", None)
    if chat_id is None or message_id is None:
        logger.info("Location choice cleanup skipped: callback message is missing.")
        return

    bot = getattr(ctx, "bot", ctx)
    text = f"✅ Выбрано: {city_label}"
    logger.info(
        "Location choice cleanup started: chat_id=%s message_id=%s label=%s",
        chat_id,
        message_id,
        city_label,
    )
    try:
        bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None,
        )
        logger.info(
            "Location choice cleanup succeeded via edit_message_text: chat_id=%s message_id=%s",
            chat_id,
            message_id,
        )
        return
    except Exception as exc:
        logger.warning(
            "Location choice cleanup edit_message_text failed: chat_id=%s message_id=%s error=%s: %s",
            chat_id,
            message_id,
            type(exc).__name__,
            exc,
        )

    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None,
        )
        logger.info(
            "Location choice cleanup succeeded via edit_message_reply_markup: chat_id=%s message_id=%s",
            chat_id,
            message_id,
        )
        return
    except Exception as exc:
        logger.warning(
            "Location choice cleanup edit_message_reply_markup failed: chat_id=%s message_id=%s error=%s: %s",
            chat_id,
            message_id,
            type(exc).__name__,
            exc,
        )

    try:
        bot.delete_message(chat_id, message_id)
        logger.info(
            "Location choice cleanup succeeded via delete_message: chat_id=%s message_id=%s",
            chat_id,
            message_id,
        )
    except Exception as exc:
        logger.warning(
            "Location choice cleanup delete_message failed: chat_id=%s message_id=%s error=%s: %s",
            chat_id,
            message_id,
            type(exc).__name__,
            exc,
        )


def return_to_location_input_context(
    chat_id: int,
    user_id: int,
    *,
    ctx,
    session_store,
    target_state: str | None,
) -> None:
    user_data = ctx.load_user(user_id)
    has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))

    location_input_states = {
        WAITING_CURRENT_WEATHER_CITY,
        WAITING_TODAY_FORECAST_CITY,
        WAITING_TOMORROW_FORECAST_CITY,
        WAITING_FORECAST_CITY,
        WAITING_DETAILS_CITY,
        WAITING_SOURCE_COMPARE_CITY,
    }

    if target_state in location_input_states:
        text = "Введи название населённого пункта или выбери другой способ ниже:"
        reply_markup = ctx.location_input_menu(has_saved_locations=has_saved)
        session_store.user_states[user_id] = target_state
        ctx.bot.send_message(chat_id, text, reply_markup=reply_markup)
        return

    prompt_map = {
        WAITING_COMPARE_CITY_1: ("Введи название первой локации.", None),
        WAITING_COMPARE_CITY_2: ("Введи название второй локации.", None),
    }

    if target_state in prompt_map:
        text, reply_markup = prompt_map[target_state]
        session_store.user_states[user_id] = target_state
        ctx.bot.send_message(chat_id, text, reply_markup=reply_markup)
        return

    session_store.user_states.pop(user_id, None)
    ctx.bot.send_message(chat_id, "Выбор отменён.", reply_markup=ctx.main_menu())
