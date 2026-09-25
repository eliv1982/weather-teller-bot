import logging
from logging.handlers import RotatingFileHandler

from utils.logging_setup import LOG_FILE_BACKUP_COUNT, LOG_FILE_MAX_BYTES, build_log_handlers


def _close(handlers):
    for handler in handlers:
        handler.close()


def test_build_log_handlers_keeps_stdout_and_uses_bounded_rotating_file(tmp_path):
    handlers = build_log_handlers(str(tmp_path / "bot.log"))
    try:
        stream_handlers = [h for h in handlers if type(h) is logging.StreamHandler]
        file_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]

        assert len(stream_handlers) == 1
        assert len(file_handlers) == 1
        (file_handler,) = file_handlers
        assert file_handler.maxBytes == LOG_FILE_MAX_BYTES > 0
        assert file_handler.backupCount == LOG_FILE_BACKUP_COUNT > 0
        assert file_handler.encoding == "utf-8"
        assert not any(type(h) is logging.FileHandler for h in handlers)
    finally:
        _close(handlers)


def test_rotating_file_handler_actually_rotates_and_keeps_utf8(tmp_path):
    log_path = tmp_path / "bot.log"
    handlers = build_log_handlers(str(log_path))
    (file_handler,) = [h for h in handlers if isinstance(h, RotatingFileHandler)]
    file_handler.maxBytes = 200  # shrink the limit so the test stays tiny
    logger = logging.getLogger("test.logging_setup.rotation")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(file_handler)
    try:
        for i in range(40):
            logger.info("строка лога №%s — проверка ротации", i)
    finally:
        logger.removeHandler(file_handler)
        _close(handlers)

    rotated = sorted(p.name for p in tmp_path.iterdir())
    assert "bot.log" in rotated
    assert "bot.log.1" in rotated
    # Never more than the configured number of backups, so disk usage stays bounded.
    assert len(rotated) <= LOG_FILE_BACKUP_COUNT + 1
    assert "проверка ротации" in log_path.read_text(encoding="utf-8")
