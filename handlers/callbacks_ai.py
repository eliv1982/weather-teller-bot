def handle_ai_callback(call, *, ctx, session_store) -> None:
    """Обрабатывает AI callback-действия для погодных сценариев."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if data == "ai_current_explain":
        ctx.bot.answer_callback_query(call.id, "✨ Данные устарели. Открой текущую погоду заново.")
        return

    if data.startswith("ai_current_explain:"):
        snapshot_id = data.split(":", 1)[1].strip()
        snapshot = session_store.ai_current_snapshots.get(snapshot_id)
        if not isinstance(snapshot, dict):
            ctx.bot.answer_callback_query(call.id, "✨ Данные устарели. Открой текущую погоду заново.")
            return
        if snapshot.get("user_id") != user_id:
            ctx.bot.answer_callback_query(call.id, "✨ Данные устарели. Открой текущую погоду заново.")
            return

        city_label = snapshot.get("city_label") or "выбранная локация"
        weather = snapshot.get("weather")
        if not isinstance(weather, dict):
            ctx.bot.answer_callback_query(call.id, "✨ Данные устарели. Открой текущую погоду заново.")
            return

        text = ctx.ai_weather_service.explain_current_weather(city_label, weather)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, f"✨ Объяснение:\n{text}", reply_markup=ctx.main_menu())
        return

    if data == "ai_details_explain":
        ctx.bot.answer_callback_query(call.id, "💡 Данные устарели. Открой расширенные данные заново.")
        return

    if data.startswith("ai_details_explain:"):
        snapshot_id = data.split(":", 1)[1].strip()
        snapshot = session_store.ai_details_snapshots.get(snapshot_id)
        if not isinstance(snapshot, dict):
            ctx.bot.answer_callback_query(call.id, "💡 Данные устарели. Открой расширенные данные заново.")
            return
        if snapshot.get("user_id") != user_id:
            ctx.bot.answer_callback_query(call.id, "💡 Данные устарели. Открой расширенные данные заново.")
            return

        city_label = snapshot.get("city_label") or "выбранная локация"
        weather = snapshot.get("weather")
        if not isinstance(weather, dict):
            ctx.bot.answer_callback_query(call.id, "💡 Данные устарели. Открой расширенные данные заново.")
            return

        air_components = snapshot.get("air_components")
        if air_components is not None and not isinstance(air_components, dict):
            air_components = None
        text = ctx.ai_weather_service.explain_weather_details(city_label, weather, air_components)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, f"💡 Пояснение:\n{text}", reply_markup=ctx.main_menu())
        return

    if data.startswith("ai_forecast_day:"):
        day = data.split(":", 1)[1]
        cache = session_store.forecast_cache.get(user_id)
        if not cache:
            ctx.bot.answer_callback_query(call.id, "🪄 Прогноз устарел. Открой его заново.")
            return

        day_items = cache.get("grouped", {}).get(day)
        if not day_items:
            ctx.bot.answer_callback_query(call.id, "Данные дня не найдены.")
            return

        city_label = cache.get("city") or "выбранная локация"
        text = ctx.ai_weather_service.summarize_day_forecast(city_label, day_items)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, f"🪄 Рекомендация на день:\n{text}", reply_markup=ctx.main_menu())
        return

    ctx.bot.answer_callback_query(call.id)
