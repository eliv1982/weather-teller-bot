"""
A manually typed "⭐ Из сохраненных" (е instead of ё) must behave like the keyboard button
"⭐ Из сохранённых" in every location-input flow, matching what the history flow already does.
"""

from types import SimpleNamespace

import pytest

from handlers.ai_compare import handle_ai_compare_text
from handlers.alerts import handle_alerts_text
from handlers.current import handle_current_text
from handlers.details import handle_details_text
from handlers.forecast import handle_forecast_text
from handlers.source_compare import handle_source_compare_text
from handlers.states import (
    WAITING_AI_COMPARE_LOC1_METHOD,
    WAITING_AI_COMPARE_LOC1_SAVED_PICK,
    WAITING_AI_COMPARE_LOC2_METHOD,
    WAITING_AI_COMPARE_LOC2_SAVED_PICK,
    WAITING_ALERTS_ADD_MENU,
    WAITING_ALERTS_ADD_SAVED_PICK,
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_CURRENT_WEATHER_SAVED_PICK,
    WAITING_DETAILS_CITY,
    WAITING_DETAILS_SAVED_PICK,
    WAITING_FORECAST_CITY,
    WAITING_FORECAST_SAVED_PICK,
    WAITING_SOURCE_COMPARE_CITY,
    WAITING_SOURCE_COMPARE_SAVED_PICK,
    WAITING_TODAY_FORECAST_CITY,
    WAITING_TODAY_FORECAST_SAVED_PICK,
    WAITING_TOMORROW_FORECAST_CITY,
    WAITING_TOMORROW_FORECAST_SAVED_PICK,
)
from session_store import SessionStore

BUTTON_YO = "⭐ Из сохранённых"
BUTTON_YE = "⭐ Из сохраненных"
SAVED = [{"id": "loc-1", "title": "Дом", "label": "Москва", "lat": 55.75, "lon": 37.61}]


class _Bot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


def _ctx(saved_locations):
    return SimpleNamespace(
        bot=_Bot(),
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        load_user=lambda user_id: {"saved_locations": saved_locations},
        build_saved_locations_keyboard=lambda locations, prefix: ("saved-keyboard", prefix),
        build_ai_compare_saved_locations_keyboard=lambda locations, step: ("ai-saved-keyboard", step),
        location_input_menu=lambda has_saved_locations=False: ("location-input-menu", has_saved_locations),
        alerts_add_location_menu=lambda has_saved_locations=False: ("alerts-add-menu", has_saved_locations),
    )


def _message(text):
    return SimpleNamespace(text=text, chat=SimpleNamespace(id=123), from_user=SimpleNamespace(id=7))


def _noop(*args, **kwargs):
    return None


def _dispatch(handler_name, message, state, ctx, session_store):
    """Calls the flow's real text handler with the dependencies it needs."""
    if handler_name == "current":
        return handle_current_text(message, 7, state, ctx=ctx, session_store=session_store)
    if handler_name == "details":
        return handle_details_text(
            message, 7, state, ctx=ctx, session_store=session_store, send_details_by_coordinates=_noop
        )
    if handler_name == "forecast":
        return handle_forecast_text(
            message,
            7,
            state,
            ctx=ctx,
            session_store=session_store,
            send_forecast_by_coordinates=_noop,
            send_today_forecast_by_coordinates=_noop,
            send_tomorrow_forecast_by_coordinates=_noop,
        )
    if handler_name == "source_compare":
        return handle_source_compare_text(
            message, 7, state, ctx=ctx, session_store=session_store, send_source_compare_by_coordinates=_noop
        )
    if handler_name == "alerts":
        return handle_alerts_text(message, 7, state, ctx=ctx, session_store=session_store)
    if handler_name == "ai_compare":
        return handle_ai_compare_text(message, 7, state, ctx=ctx, session_store=session_store)
    raise AssertionError(handler_name)


FLOWS = [
    pytest.param("current", WAITING_CURRENT_WEATHER_CITY, WAITING_CURRENT_WEATHER_SAVED_PICK, id="current"),
    pytest.param("details", WAITING_DETAILS_CITY, WAITING_DETAILS_SAVED_PICK, id="details"),
    pytest.param("forecast", WAITING_FORECAST_CITY, WAITING_FORECAST_SAVED_PICK, id="forecast-5days"),
    pytest.param("forecast", WAITING_TODAY_FORECAST_CITY, WAITING_TODAY_FORECAST_SAVED_PICK, id="forecast-today"),
    pytest.param(
        "forecast", WAITING_TOMORROW_FORECAST_CITY, WAITING_TOMORROW_FORECAST_SAVED_PICK, id="forecast-tomorrow"
    ),
    pytest.param("source_compare", WAITING_SOURCE_COMPARE_CITY, WAITING_SOURCE_COMPARE_SAVED_PICK, id="source-compare"),
    pytest.param("alerts", WAITING_ALERTS_ADD_MENU, WAITING_ALERTS_ADD_SAVED_PICK, id="alerts-add"),
    pytest.param("ai_compare", WAITING_AI_COMPARE_LOC1_METHOD, WAITING_AI_COMPARE_LOC1_SAVED_PICK, id="ai-compare-loc1"),
    pytest.param("ai_compare", WAITING_AI_COMPARE_LOC2_METHOD, WAITING_AI_COMPARE_LOC2_SAVED_PICK, id="ai-compare-loc2"),
]


@pytest.mark.parametrize(("handler_name", "state", "saved_pick_state"), FLOWS)
@pytest.mark.parametrize("button_text", [BUTTON_YO, BUTTON_YE], ids=["yo-button", "ye-typed"])
def test_saved_locations_button_routes_to_saved_pick_with_or_without_yo(
    handler_name, state, saved_pick_state, button_text
):
    ctx = _ctx(SAVED)
    session_store = SessionStore()
    session_store.user_states[7] = state

    handled = _dispatch(handler_name, _message(button_text), state, ctx, session_store)

    assert handled is True
    assert session_store.user_states[7] == saved_pick_state
    assert len(ctx.bot.messages) == 1
    assert isinstance(ctx.bot.messages[0]["reply_markup"], tuple)
    assert ctx.bot.messages[0]["reply_markup"][0] in {"saved-keyboard", "ai-saved-keyboard"}


@pytest.mark.parametrize(("handler_name", "state", "saved_pick_state"), FLOWS)
@pytest.mark.parametrize("button_text", [BUTTON_YO, BUTTON_YE], ids=["yo-button", "ye-typed"])
def test_saved_locations_button_without_saved_locations_reports_empty_list_with_or_without_yo(
    handler_name, state, saved_pick_state, button_text
):
    ctx = _ctx([])
    session_store = SessionStore()
    session_store.user_states[7] = state

    handled = _dispatch(handler_name, _message(button_text), state, ctx, session_store)

    assert handled is True
    assert session_store.user_states[7] == state
    assert [m["text"] for m in ctx.bot.messages] == ["Сохранённых локаций пока нет."]


@pytest.mark.parametrize("button_text", ["Из сохранённых", "Из сохраненных"], ids=["yo-plain", "ye-plain"])
@pytest.mark.parametrize(
    ("state", "saved_pick_state"),
    [
        (WAITING_AI_COMPARE_LOC1_METHOD, WAITING_AI_COMPARE_LOC1_SAVED_PICK),
        (WAITING_AI_COMPARE_LOC2_METHOD, WAITING_AI_COMPARE_LOC2_SAVED_PICK),
    ],
)
def test_ai_compare_plain_saved_locations_text_accepts_yo_and_ye(button_text, state, saved_pick_state):
    ctx = _ctx(SAVED)
    session_store = SessionStore()

    handled = _dispatch("ai_compare", _message(button_text), state, ctx, session_store)

    assert handled is True
    assert session_store.user_states[7] == saved_pick_state
