from .callbacks_common import mark_location_choice_selected, return_to_location_input_context
from .states import WAITING_CURRENT_WEATHER_CITY


def handle_current_weather_callback(
    call,
    *,
    ctx,
    session_store,
) -> None:
    """Обрабатывает выбор локации или отмену в сценарии «Текущая погода»."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "current_cancel":
        session_store.current_location_choices.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        return_to_location_input_context(
            chat_id,
            user_id,
            ctx=ctx,
            session_store=session_store,
            target_state=WAITING_CURRENT_WEATHER_CITY,
        )
        return

    if call.data.startswith("current_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.current_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        choices = session_store.current_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.current_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        location_item = ctx.build_geocode_item_with_disambiguated_label(choices, index)
        ctx.logger.info(
            "Пользователь %s выбрал вариант текущей погоды #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        ctx.bot.answer_callback_query(call.id)
        mark_location_choice_selected(call, ctx, str(location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)))
        ctx.complete_current_weather_from_location(
            ctx.bot,
            chat_id,
            user_id,
            location_item,
            user_states=session_store.user_states,
            current_location_choices=session_store.current_location_choices,
            ai_current_snapshots=session_store.ai_current_snapshots,
            create_ai_snapshot_id_fn=session_store.generate_ai_snapshot_id,
            cleanup_ai_snapshots_fn=session_store.cleanup_ai_snapshots,
            load_user_fn=ctx.load_user,
            save_user_fn=ctx.save_user,
        )
        return

    if call.data.startswith("current_saved_pick:"):
        location_id = call.data.split(":", 1)[1] if ":" in call.data else ""
        user_data = ctx.load_user(user_id)
        saved_locations = user_data.get("saved_locations", [])
        target = next(
            (
                item
                for item in saved_locations
                if isinstance(item, dict) and isinstance(location_id, str) and item.get("id") == location_id
            ),
            None,
        )
        if not isinstance(target, dict):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(chat_id, "⚠️ Сохранённая локация не найдена.", reply_markup=ctx.main_menu())
            return
        location_item = {
            "lat": target.get("lat"),
            "lon": target.get("lon"),
            "label": target.get("label") or target.get("title") or "Сохранённая локация",
        }
        ctx.bot.answer_callback_query(call.id)
        mark_location_choice_selected(call, ctx, str(location_item["label"]))
        ctx.complete_current_weather_from_location(
            ctx.bot,
            chat_id,
            user_id,
            location_item,
            user_states=session_store.user_states,
            current_location_choices=session_store.current_location_choices,
            ai_current_snapshots=session_store.ai_current_snapshots,
            create_ai_snapshot_id_fn=session_store.generate_ai_snapshot_id,
            cleanup_ai_snapshots_fn=session_store.cleanup_ai_snapshots,
            load_user_fn=ctx.load_user,
            save_user_fn=ctx.save_user,
        )
        return

    ctx.bot.answer_callback_query(call.id)
