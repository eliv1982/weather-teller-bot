from callbacks.constants import (
    SOURCE_COMPARE_CANCEL,
    SOURCE_COMPARE_DATE_CANCEL,
    SOURCE_COMPARE_DATE_ANOTHER,
    SOURCE_COMPARE_PICK_PREFIX,
    SOURCE_COMPARE_SAVED_PICK_PREFIX,
    SOURCE_COMPARE_DATE_PICK_PREFIX,
)

from .callbacks_common import mark_location_choice_selected, return_to_location_input_context
from .states import WAITING_SOURCE_COMPARE_CITY, WAITING_SOURCE_COMPARE_DATE_PICK


def handle_source_compare_callback(
    call,
    *,
    ctx,
    session_store,
    send_source_compare_by_coordinates,
    send_source_compare_by_selected_date,
    _message_stub_for_chat,
) -> None:
    """Handles inline location choice for source-compare flow."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == SOURCE_COMPARE_CANCEL:
        session_store.source_compare_location_choices.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        return_to_location_input_context(
            chat_id,
            user_id,
            ctx=ctx,
            session_store=session_store,
            target_state=WAITING_SOURCE_COMPARE_CITY,
        )
        return

    if call.data.startswith(f"{SOURCE_COMPARE_PICK_PREFIX}:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.source_compare_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        choices = session_store.source_compare_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.source_compare_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        location_item = ctx.build_geocode_item_with_disambiguated_label(choices, index)
        city = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        if lat is None or lon is None:
            session_store.source_compare_location_choices.pop(user_id, None)
            session_store.user_states.pop(user_id, None)
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "Не удалось сравнить источники: один из прогнозов сейчас недоступен.",
                reply_markup=ctx.main_menu(),
            )
            return
        ctx.bot.answer_callback_query(call.id)
        mark_location_choice_selected(call, ctx, str(city))
        stub = _message_stub_for_chat(chat_id)
        send_source_compare_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        return

    if call.data.startswith(f"{SOURCE_COMPARE_SAVED_PICK_PREFIX}:"):
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
        lat = target.get("lat")
        lon = target.get("lon")
        city = str(target.get("label") or target.get("title") or "Сохранённая локация")
        if lat is None or lon is None:
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(chat_id, "⚠️ У сохранённой локации нет координат.", reply_markup=ctx.main_menu())
            return
        ctx.bot.answer_callback_query(call.id)
        mark_location_choice_selected(call, ctx, city)
        stub = _message_stub_for_chat(chat_id)
        send_source_compare_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        return

    if call.data == SOURCE_COMPARE_DATE_CANCEL:
        session_store.source_compare_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Выбор даты отменён.", reply_markup=ctx.main_menu())
        return

    if call.data == SOURCE_COMPARE_DATE_ANOTHER:
        draft = session_store.source_compare_drafts.get(user_id)
        if not isinstance(draft, dict):
            ctx.bot.answer_callback_query(call.id, "Данные устарели. Начни сравнение заново.")
            return
        available_days = draft.get("available_days")
        city_label = str(draft.get("city_label") or "локации")
        if not isinstance(available_days, list) or not available_days:
            ctx.bot.answer_callback_query(call.id, "Даты недоступны.")
            return
        session_store.user_states[user_id] = WAITING_SOURCE_COMPARE_DATE_PICK
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(
            chat_id,
            f"Выбери дату прогноза для {city_label}:",
            reply_markup=ctx.build_source_compare_days_keyboard(available_days),
        )
        return

    if call.data.startswith(f"{SOURCE_COMPARE_DATE_PICK_PREFIX}:"):
        selected_day = call.data.split(":", 1)[1] if ":" in call.data else ""
        draft = session_store.source_compare_drafts.get(user_id)
        if not isinstance(draft, dict):
            ctx.bot.answer_callback_query(call.id, "Данные устарели. Начни сравнение заново.")
            return
        available_days = draft.get("available_days")
        if not isinstance(available_days, list) or selected_day not in available_days:
            ctx.bot.answer_callback_query(call.id, "Дата недоступна.")
            return
        ctx.bot.answer_callback_query(call.id)
        mark_location_choice_selected(call, ctx, selected_day)
        stub = _message_stub_for_chat(chat_id)
        send_source_compare_by_selected_date(
            stub,
            user_id,
            selected_day,
        )
        return

    ctx.bot.answer_callback_query(call.id)
