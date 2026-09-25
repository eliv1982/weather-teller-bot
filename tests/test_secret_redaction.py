"""A Telegram bot token must never reach application log output, even when a library embeds the request URL."""

import importlib
import io
import logging
import sys
import types
from urllib.parse import quote

import pytest
import requests
import telebot
from telebot import apihelper

import utils.logging_setup as logging_setup
from utils.logging_setup import SecretRedactionFilter, build_log_handlers, protect_library_loggers, register_secret

# Deliberately full of regex-significant characters: redaction must be a literal match, not a pattern.
FAKE_TOKEN = "123456789:AAF+[x](y)*z?.$^|{1}\\-Q_"
PLACEHOLDER = "[REDACTED:BOT_TOKEN]"


def _network_error(url_path: str) -> requests.ConnectionError:
    # Mirrors the real requests/urllib3 message, which embeds the full request URL.
    return requests.ConnectionError(
        "HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded with url: "
        f"{url_path}?offset=-1&timeout=20 (Caused by NewConnectionError('Failed to establish a new connection'))"
    )


@pytest.fixture
def redactor(monkeypatch):
    fresh = SecretRedactionFilter()
    monkeypatch.setattr(logging_setup, "SECRET_REDACTOR", fresh)
    yield fresh
    telebot_logger = logging.getLogger("TeleBot")
    telebot_logger.removeFilter(fresh)
    for handler in telebot_logger.handlers:
        handler.removeFilter(fresh)


@pytest.fixture
def app_logger(tmp_path, redactor):
    """A logger wired exactly like the application: build_log_handlers() = stderr stream + rotating file."""
    log_path = tmp_path / "bot.log"
    handlers = build_log_handlers(str(log_path))
    stream = io.StringIO()
    handlers[0].setStream(stream)
    logger = logging.getLogger("test.secret_redaction.app")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in handlers:
        handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
        logger.addHandler(handler)
    register_secret(FAKE_TOKEN, "BOT_TOKEN")

    def output() -> str:
        for handler in handlers:
            handler.flush()
        return stream.getvalue() + "\n" + log_path.read_text(encoding="utf-8")

    yield logger, output
    for handler in handlers:
        logger.removeHandler(handler)
        handler.close()


def test_library_style_message_with_token_url_is_redacted_but_stays_diagnosable(app_logger):
    logger, output = app_logger
    error = _network_error(f"/bot{FAKE_TOKEN}/getUpdates")

    logger.error("Infinity polling exception: %s", error)

    text = output()
    assert FAKE_TOKEN not in text
    assert f"/bot{PLACEHOLDER}/getUpdates" in text
    assert "Max retries exceeded" in text  # the useful part of the diagnostics survives


def test_traceback_of_chained_exceptions_with_token_url_is_redacted(app_logger):
    logger, output = app_logger

    try:
        try:
            raise _network_error(f"/bot{FAKE_TOKEN}/getUpdates")
        except requests.ConnectionError as exc:
            raise RuntimeError(f"polling failed: {exc}") from exc
    except RuntimeError:
        logger.exception("Polling остановлен из-за необработанной ошибки.")

    text = output()
    assert FAKE_TOKEN not in text
    assert "Traceback (most recent call last)" in text
    assert "requests.exceptions.ConnectionError" in text
    assert "RuntimeError: polling failed" in text
    assert PLACEHOLDER in text


def test_percent_encoded_token_is_redacted(app_logger):
    logger, output = app_logger

    logger.warning("GET /bot%s/getMe", quote(FAKE_TOKEN, safe=""))
    logger.warning("GET /bot%s/getMe", quote(FAKE_TOKEN))

    text = output()
    assert quote(FAKE_TOKEN, safe="") not in text
    assert quote(FAKE_TOKEN) not in text
    lines = [line for line in text.splitlines() if "/getMe" in line]
    assert lines and all(f"/bot{PLACEHOLDER}/getMe" in line for line in lines)


def test_redaction_is_a_literal_match_not_a_regex():
    flt = SecretRedactionFilter()
    flt.add_secret("abc.def*ghi+jkl(mno", "K")

    assert flt.redact("x abc.def*ghi+jkl(mno y") == "x [REDACTED:K] y"
    # A regex would treat '.' as "any char" and match this near-miss.
    assert flt.redact("abcXdef*ghi+jkl(mno") == "abcXdef*ghi+jkl(mno"


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_blank_secret_is_ignored_and_does_not_corrupt_messages(blank):
    flt = SecretRedactionFilter()
    flt.add_secret(blank, "K")

    assert flt.redact("plain message with spaces") == "plain message with spaces"


def test_record_without_secret_is_left_untouched(app_logger):
    logger, output = app_logger

    logger.info("user=%s count=%d", "alice", 3)

    assert "user=alice count=3" in output()


def test_real_telebot_url_path_is_redacted_on_startup_failure_and_library_logger(monkeypatch, caplog, app_logger):
    """Drives the installed pyTelegramBotAPI so the URL shape comes from the library, not from the test."""
    logger, output = app_logger
    seen_urls = []

    def failing_sender(method, url, **kwargs):
        seen_urls.append(url)
        raise _network_error(url.split("api.telegram.org", 1)[1])

    monkeypatch.setattr(apihelper, "CUSTOM_REQUEST_SENDER", failing_sender)
    bot = telebot.TeleBot(FAKE_TOKEN)

    # bot.py calls infinity_polling(skip_pending=True): the startup call runs outside the library's own try/except.
    with pytest.raises(requests.ConnectionError) as excinfo:
        try:
            bot.infinity_polling(skip_pending=True)
        except requests.ConnectionError:
            logger.exception("Polling остановлен из-за необработанной ошибки.")
            raise
    assert seen_urls and FAKE_TOKEN in seen_urls[0]
    assert FAKE_TOKEN in str(excinfo.value)  # sanity: the raw exception really does carry the token

    assert FAKE_TOKEN not in output()
    assert f"/bot{PLACEHOLDER}/getUpdates" in output()
    assert "Traceback (most recent call last)" in output()

    # The library's own logger also has its own stderr handler, outside build_log_handlers().
    library_stderr = io.StringIO()
    monkeypatch.setattr(telebot.console_output_handler, "stream", library_stderr)
    protect_library_loggers()
    with caplog.at_level(logging.ERROR, logger="TeleBot"):
        telebot.logger.error("Polling exception: %s", excinfo.value)
        try:
            raise excinfo.value
        except requests.ConnectionError:
            telebot.logger.exception("Exception traceback:")

    assert FAKE_TOKEN not in library_stderr.getvalue()
    assert FAKE_TOKEN not in caplog.text
    assert PLACEHOLDER in library_stderr.getvalue()


def test_build_log_handlers_attach_the_shared_redaction_filter(redactor, tmp_path):
    handlers = build_log_handlers(str(tmp_path / "bot.log"))
    try:
        for handler in handlers:
            assert redactor in handler.filters
    finally:
        for handler in handlers:
            handler.close()


def test_importing_bot_registers_the_token_for_redaction(monkeypatch, redactor):
    telebot_module = types.ModuleType("telebot")
    telebot_module.TeleBot = lambda token: types.SimpleNamespace(
        token=token,
        message_handler=lambda *a, **k: (lambda func: func),
        callback_query_handler=lambda *a, **k: (lambda func: func),
    )
    telebot_module.types = types.SimpleNamespace(
        Message=object,
        CallbackQuery=object,
        ReplyKeyboardMarkup=object,
        KeyboardButton=object,
        InlineKeyboardMarkup=object,
        InlineKeyboardButton=object,
        ReplyKeyboardRemove=lambda: "reply-keyboard-remove",
    )
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda: None
    monkeypatch.setenv("BOT_TOKEN", FAKE_TOKEN)
    monkeypatch.setitem(sys.modules, "telebot", telebot_module)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv_module)
    sys.modules.pop("bot", None)
    try:
        importlib.import_module("bot")
    finally:
        sys.modules.pop("bot", None)

    assert redactor.redact(f"url: /bot{FAKE_TOKEN}/getUpdates") == f"url: /bot{PLACEHOLDER}/getUpdates"
