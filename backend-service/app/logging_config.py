import json
import logging
import logging.handlers
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from app.config import LOG_DIR, LOG_FILE, LOG_LEVEL, LOG_RETENTION_DAYS

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_RESERVED_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "request_id",
}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "-"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    DIM = "\033[2m"

    LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")
        request_id = getattr(record, "request_id", "-")
        prefix = (
            f"{self.DIM}{timestamp} [{request_id}]{self.RESET} "
            f"{color}{record.levelname:<8}{self.RESET}"
        )
        line = f"{prefix} {record.name}: {record.getMessage()}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL.upper())
    root.handlers.clear()

    formatter = JsonFormatter()
    request_filter = RequestIdFilter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(ColorFormatter() if sys.stdout.isatty() else formatter)
    stream_handler.addFilter(request_filter)
    root.addHandler(stream_handler)

    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(LOG_DIR, LOG_FILE),
        when="midnight",
        backupCount=LOG_RETENTION_DAYS,
        utc=True,
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_filter)
    root.addHandler(file_handler)
