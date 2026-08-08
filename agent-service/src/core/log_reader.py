import glob
import json
import os
from datetime import datetime, timezone

from core.config import settings


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _log_file_paths() -> list[str]:
    base = os.path.join(settings.log_dir, settings.log_file)
    paths = [base] + glob.glob(base + ".*")
    paths = [p for p in paths if os.path.exists(p)]
    paths.sort(key=os.path.getmtime)
    return paths


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def read_session_logs(
    session_id: str,
    level: str | None,
    logger: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    start_time = _as_utc(start_time)
    end_time = _as_utc(end_time)
    matches: list[dict] = []

    for path in _log_file_paths():
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("session_id") != session_id:
                    continue
                if level is not None and entry.get("level") != level:
                    continue
                if logger is not None and entry.get("logger") != logger:
                    continue

                if start_time is not None or end_time is not None:
                    try:
                        entry_time = _parse_timestamp(entry["timestamp"])
                    except (KeyError, ValueError):
                        continue
                    if start_time is not None and entry_time < start_time:
                        continue
                    if end_time is not None and entry_time > end_time:
                        continue

                matches.append(entry)

    matches.sort(key=lambda entry: entry.get("timestamp", ""))
    total = len(matches)
    return matches[offset : offset + limit], total
