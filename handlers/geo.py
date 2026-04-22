def handle_geo_text(
    message,
    user_id: int,
    state: str | None,
    *,
    WAITING_GEO_LOCATION,
    bot,
    user_states: dict,
    compare_drafts: dict,
    details_location_choices: dict,
    forecast_location_choices: dict,
    compare_location_choices: dict,
    main_menu,
    geo_request_menu,
) -> bool:
    """Обрабатывает текстовый сценарий ожидания геолокации."""
    if state != WAITING_GEO_LOCATION:
        return False

    if message.text == "⬅️ В меню":
        user_states.pop(user_id, None)
        compare_drafts.pop(user_id, None)
        details_location_choices.pop(user_id, None)
        forecast_location_choices.pop(user_id, None)
        compare_location_choices.pop(user_id, None)
        bot.send_message(message.chat.id, "Главное меню.", reply_markup=main_menu())
        return True

    bot.send_message(
        message.chat.id,
        "Пожалуйста, отправь геолокацию через кнопку ниже.\n"
        "Если ты используешь Telegram Desktop, открой бота на телефоне или вернись в меню.",
        reply_markup=geo_request_menu(),
    )
    return True
