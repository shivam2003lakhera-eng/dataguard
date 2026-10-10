import logging
import sys

from app.core.config import get_settings

_SENSITIVE_WORDS = ("password", "token", "secret", "authorization", "api_key")


class RedactSecretsFilter(logging.Filter):
    """Blocks log messages that appear to contain secrets."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        if any(word in message for word in _SENSITIVE_WORDS):
            record.msg = "[log message hidden: may contain a secret]"
            record.args = ()
        return True


def setup_logging() -> None:
    """Configure logging for the whole application. Call once at startup."""
    settings = get_settings()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    handler.addFilter(RedactSecretsFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Use get_logger(__name__) in every module."""
    return logging.getLogger(name)