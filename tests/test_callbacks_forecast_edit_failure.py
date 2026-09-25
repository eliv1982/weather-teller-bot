"""A Telegram edit failure in the forecast callbacks must never leave the callback unanswered."""

from types import SimpleNamespace

import pytest

from callbacks.constants import FORECAST_BACK, FORECAST_DAY_PREFIX
from handlers.callbacks_forecast import handle_forecast_callback

SECRET_IN_ERROR = "123456:BOT-TOKEN-MARKER"


class _Bot:
    def __init__(self, *, edit_error: Exception | None = None):
        self.calls = []
        self._edit_error = edit_error

    def edit_message_text(self, *args, **kwargs):
        self.calls.append(("edit_message_text", args, kwargs))
        if self._edit_error is not None:
            raise self._edit_error

    def answer_callback_query(self, *args, **kwargs):
        self.calls.append(("answer_callback_query", args, kwargs))

    def send_message(self, *args, **kwargs):
        self.calls.append(("send_message", args, kwargs))

    def names(self):
        return [name for name, _args, _kwargs in self.calls]


class _Logger:
    def __init__(self):
        self.warnings = []

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        self.warnings.append(args)


def _call(data: str):
    return SimpleNamespace(
        id="callback-id",
        data=data,
        from_user=SimpleNamespace(id=1),
        message=SimpleNamespace(chat=SimpleNamespace(id=100), message_id=200),
    )


def _ctx(bot, logger):
    return SimpleNamespace(
        bot=bot,
        logger=logger,
        build_forecast_days_keyboard=lambda days: ("days-keyboard", tuple(days)),
        build_forecast_day_keyboard=lambda days, day: ("day-keyboard", tuple(days), day),
        format_forecast_day=lambda day, items, city: f"forecast {day} for {city}",
    )


def _session_store():
    return SimpleNamespace(
        user_states={},
        forecast_saved_drafts={},
        forecast_location_choices={},
        forecast_cache={1: {"city": "Москва", "grouped": {"03.05": [{"dt": 1}], "04.05": [{"dt": 2}]}}},
        get_state=lambda user_id: None,
    )


def _run(call, ctx, session_store):
    handle_forecast_callback(
        call,
        ctx=ctx,
        session_store=session_store,
        _message_stub_for_chat=lambda chat_id: None,
        send_forecast_by_coordinates=lambda *a, **k: None,
        send_today_forecast_by_coordinates=lambda *a, **k: None,
        send_tomorrow_forecast_by_coordinates=lambda *a, **k: None,
    )


@pytest.mark.parametrize(
    "callback_data",
    [FORECAST_BACK, f"{FORECAST_DAY_PREFIX}:03.05"],
    ids=["back-to-days", "day-selected"],
)
@pytest.mark.parametrize(
    "edit_error",
    [
        RuntimeError("Bad Request: message is not modified"),
        ConnectionError(f"HTTPSConnectionPool: url: /bot{SECRET_IN_ERROR}/editMessageText"),
    ],
    ids=["telegram-api-error", "network-error"],
)
def test_forecast_callback_edit_failure_still_answers_callback(callback_data, edit_error):
    bot = _Bot(edit_error=edit_error)
    logger = _Logger()

    _run(_call(callback_data), _ctx(bot, logger), _session_store())

    assert bot.names() == ["edit_message_text", "answer_callback_query"]
    assert bot.calls[1][1] == ("callback-id",)
    assert len(logger.warnings) == 1
    # Only the exception type is logged: network errors can embed the bot token in the URL.
    logged = " ".join(str(part) for part in logger.warnings[0])
    assert type(edit_error).__name__ in logged
    assert SECRET_IN_ERROR not in logged


@pytest.mark.parametrize(
    ("callback_data", "expected_text", "expected_markup"),
    [
        (FORECAST_BACK, "Выбери день прогноза для Москва:", ("days-keyboard", ("03.05", "04.05"))),
        (f"{FORECAST_DAY_PREFIX}:03.05", "forecast 03.05 for Москва", ("day-keyboard", ("03.05", "04.05"), "03.05")),
    ],
    ids=["back-to-days", "day-selected"],
)
def test_forecast_callback_happy_path_edits_then_answers(callback_data, expected_text, expected_markup):
    bot = _Bot()
    logger = _Logger()

    _run(_call(callback_data), _ctx(bot, logger), _session_store())

    assert bot.names() == ["edit_message_text", "answer_callback_query"]
    _name, _args, kwargs = bot.calls[0]
    assert kwargs == {
        "chat_id": 100,
        "message_id": 200,
        "text": expected_text,
        "reply_markup": expected_markup,
    }
    assert logger.warnings == []
