import logging


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
