import json
import logging
import logging.handlers
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from core.config import settings

session_id_var: ContextVar[str] = ContextVar("session_id", default="-")

_RESERVED_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "session_id",
}


class SessionIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = session_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "session_id": getattr(record, "session_id", "-"),
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
    ROLE_COLORS = {
        "human": "\033[34m",
        "ai": "\033[35m",
        "tool": "\033[36m",
    }

    def format(self, record: logging.LogRecord) -> str:
        role = getattr(record, "role", None)
        color = self.ROLE_COLORS.get(role) or self.LEVEL_COLORS.get(record.levelno, "")
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")
        session_id = getattr(record, "session_id", "-")
        prefix = (
            f"{self.DIM}{timestamp} [{session_id}]{self.RESET} "
            f"{color}{record.levelname:<8}{self.RESET}"
        )

        if role:
            line = f"{prefix} {color}{role}{self.RESET}: {record.getMessage()}"
            tool_calls = getattr(record, "tool_calls", None)
            if tool_calls:
                line += f" {self.DIM}tool_calls={tool_calls}{self.RESET}"
        else:
            line = f"{prefix} {record.name}: {record.getMessage()}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    formatter = JsonFormatter()
    session_filter = SessionIdFilter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(ColorFormatter() if sys.stdout.isatty() else formatter)
    stream_handler.addFilter(session_filter)
    root.addHandler(stream_handler)

    os.makedirs(settings.log_dir, exist_ok=True)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(settings.log_dir, settings.log_file),
        when="midnight",
        backupCount=settings.log_retention_days,
        utc=True,
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(session_filter)
    root.addHandler(file_handler)
