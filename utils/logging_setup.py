import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import quote, quote_plus

LOG_FILE_NAME = "bot.log"
LOG_FILE_MAX_BYTES = 5 * 1024 * 1024
LOG_FILE_BACKUP_COUNT = 3

# Логгеры сторонних библиотек со своими хендлерами (pyTelegramBotAPI ставит собственный stderr-хендлер),
# которые не проходят через build_log_handlers().
LIBRARY_LOGGER_NAMES = ("TeleBot",)


class SecretRedactionFilter(logging.Filter):
    """Заменяет зарегистрированные секреты на плейсхолдер в тексте записи и в traceback.

    Сообщения сетевых ошибок (requests/urllib3, pyTelegramBotAPI) содержат URL вида /bot<TOKEN>/method,
    поэтому токен может попасть в лог из любого места, включая сторонние библиотеки.
    Замена делается обычным str.replace, без regex: спецсимволы в значении секрета безопасны.
    """

    def __init__(self) -> None:
        super().__init__()
        self._replacements: list[tuple[str, str]] = []

    def add_secret(self, secret: str | None, label: str = "SECRET") -> None:
        if not secret or not secret.strip():
            return
        placeholder = f"[REDACTED:{label}]"
        # Секрет может встретиться в URL в исходном виде или в percent-encoded виде.
        for variant in {secret, quote(secret), quote(secret, safe=""), quote_plus(secret)}:
            if variant and all(variant != known for known, _ in self._replacements):
                self._replacements.append((variant, placeholder))
        # Сначала длинные варианты, чтобы более короткий не разрезал более длинный.
        self._replacements.sort(key=lambda item: len(item[0]), reverse=True)

    def redact(self, text: str) -> str:
        for secret, placeholder in self._replacements:
            text = text.replace(secret, placeholder)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._replacements:
            return True

        try:
            message = record.getMessage()
        except Exception:
            # Некорректный формат/аргументы: пусть с этим разбирается штатная обработка ошибок logging.
            return True
        redacted_message = self.redact(message)
        if redacted_message != message:
            record.msg = redacted_message
            record.args = None

        # Formatter использует record.exc_text, если он уже заполнен, поэтому кладем туда очищенный traceback.
        if record.exc_info:
            record.exc_text = self.redact(record.exc_text or logging.Formatter().formatException(record.exc_info))
        elif record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        if record.stack_info:
            record.stack_info = self.redact(record.stack_info)
        return True


SECRET_REDACTOR = SecretRedactionFilter()


def register_secret(secret: str | None, label: str = "SECRET") -> None:
    """Регистрирует значение, которое не должно попасть в логи приложения."""
    SECRET_REDACTOR.add_secret(secret, label)


def protect_library_loggers(names: tuple[str, ...] = LIBRARY_LOGGER_NAMES) -> None:
    """Подключает фильтр к логгерам библиотек и их собственным хендлерам."""
    for name in names:
        library_logger = logging.getLogger(name)
        library_logger.addFilter(SECRET_REDACTOR)
        for handler in library_logger.handlers:
            handler.addFilter(SECRET_REDACTOR)


def build_log_handlers(log_path: str = LOG_FILE_NAME) -> list[logging.Handler]:
    """Возвращает stdout-хендлер и файловый хендлер с ротацией (лимит ~20 МБ на диске)."""
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        RotatingFileHandler(
            log_path,
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        ),
    ]
    for handler in handlers:
        handler.addFilter(SECRET_REDACTOR)
    return handlers
