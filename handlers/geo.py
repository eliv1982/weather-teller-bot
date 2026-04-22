def handle_geo_text(
    message,
    user_id: int,
    state: str | None,
    *,
    WAITING_GEO_LOCATION,
    ctx,
    session_store,
) -> bool:
    """Обрабатывает текстовый сценарий ожидания геолокации."""
    if state != WAITING_GEO_LOCATION:
        return False

    if message.text == "⬅️ В меню":
        session_store.clear_state(user_id)
        session_store.compare_drafts.pop(user_id, None)
        session_store.details_location_choices.pop(user_id, None)
        session_store.forecast_location_choices.pop(user_id, None)
        session_store.compare_location_choices.pop(user_id, None)
        ctx.bot.send_message(message.chat.id, "Главное меню.", reply_markup=ctx.main_menu())
        return True

    ctx.bot.send_message(
        message.chat.id,
        "Пожалуйста, отправь геолокацию через кнопку ниже.\n"
        "Если ты используешь Telegram Desktop, открой бота на телефоне или вернись в меню.",
        reply_markup=ctx.geo_request_menu(),
    )
    return True
