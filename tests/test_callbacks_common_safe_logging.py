"""
Telegram cleanup helpers must never write raw exception text to the logs.

Network errors raised by the Telegram client (``requests``) embed the request URL, which for the
Bot API is ``/bot<TOKEN>/<method>``. Only the exception type may be logged.
"""

import logging
from types import SimpleNamespace

from handlers.callbacks_common import (
    clear_inline_choice_message,
    mark_location_choice_selected,
    try_delete_message,
)

SECRET_IN_ERROR = "123456:BOT-TOKEN-MARKER"
LOGGER_NAME = "handlers.callbacks_common"


class _NetworkError(Exception):
    """Stands in for requests.ConnectionError: str() contains the token-bearing URL."""

    def __init__(self, method: str):
        super().__init__(
            "HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded "
            f"with url: /bot{SECRET_IN_ERROR}/{method}"
        )


class _FailingBot:
    """Every Telegram call fails with a token-bearing network error."""

    def __init__(self):
        self.calls = []

    def _fail(self, method):
        self.calls.append(method)
        raise _NetworkError(method)

    def edit_message_text(self, *args, **kwargs):
        self._fail("editMessageText")

    def edit_message_reply_markup(self, *args, **kwargs):
        self._fail("editMessageReplyMarkup")

    def delete_message(self, *args, **kwargs):
        self._fail("deleteMessage")


def _call():
    return SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(id=100), message_id=200))


def _assert_no_secret_anywhere(caplog):
    assert caplog.records, "expected the failure to be logged"
    assert SECRET_IN_ERROR not in caplog.text
    for record in caplog.records:
        assert SECRET_IN_ERROR not in record.getMessage()
        assert SECRET_IN_ERROR not in str(record.args)
        assert record.exc_info is None  # a traceback would carry the exception message too


def _warnings(caplog):
    return [r for r in caplog.records if r.levelno == logging.WARNING]


def test_mark_location_choice_selected_logs_no_secret_and_keeps_context(caplog):
    bot = _FailingBot()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        mark_location_choice_selected(_call(), SimpleNamespace(bot=bot), "Москва")

    # All three fallbacks (edit text -> edit markup -> delete) were attempted and each failure was logged.
    assert bot.calls == ["editMessageText", "editMessageReplyMarkup", "deleteMessage"]
    _assert_no_secret_anywhere(caplog)
    warnings = _warnings(caplog)
    assert len(warnings) == 3
    for record in warnings:
        message = record.getMessage()
        assert "chat_id=100" in message
        assert "message_id=200" in message
        assert "_NetworkError" in message
    assert "edit_message_text failed" in warnings[0].getMessage()
    assert "edit_message_reply_markup failed" in warnings[1].getMessage()
    assert "delete_message failed" in warnings[2].getMessage()


def test_clear_inline_choice_message_logs_no_secret_and_keeps_context(caplog):
    bot = _FailingBot()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        clear_inline_choice_message(_call(), SimpleNamespace(bot=bot))

    assert bot.calls == ["deleteMessage", "editMessageReplyMarkup"]
    _assert_no_secret_anywhere(caplog)
    warnings = _warnings(caplog)
    assert len(warnings) == 2
    for record in warnings:
        message = record.getMessage()
        assert "chat_id=100" in message
        assert "message_id=200" in message
        assert "_NetworkError" in message


def test_try_delete_message_logs_no_secret_even_at_debug_level(caplog):
    bot = _FailingBot()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        try_delete_message(SimpleNamespace(bot=bot), 100, 200)  # must not raise

    assert bot.calls == ["deleteMessage"]
    _assert_no_secret_anywhere(caplog)
    (record,) = caplog.records
    assert record.levelno == logging.DEBUG
    assert "chat_id=100" in record.getMessage()
    assert "message_id=200" in record.getMessage()
    assert "_NetworkError" in record.getMessage()


def test_cleanup_success_paths_do_not_log_warnings(caplog):
    class _OkBot:
        def edit_message_text(self, *args, **kwargs):
            pass

        def delete_message(self, *args, **kwargs):
            pass

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        mark_location_choice_selected(_call(), SimpleNamespace(bot=_OkBot()), "Москва")
        clear_inline_choice_message(_call(), SimpleNamespace(bot=_OkBot()))
        try_delete_message(SimpleNamespace(bot=_OkBot()), 100, 200)

    assert _warnings(caplog) == []
