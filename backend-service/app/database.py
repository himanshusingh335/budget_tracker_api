import sqlite3
from typing import Generator

from app.config import DB_PATH


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create tables that the app owns outright (the legacy tables pre-exist in the prod DB)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_transactions (
                id          INTEGER PRIMARY KEY,
                Date        TEXT    NOT NULL,
                Description TEXT    NOT NULL,
                Type        TEXT    NOT NULL,
                Amount      REAL    NOT NULL,
                Account     TEXT,
                Year        INTEGER NOT NULL,
                Month       INTEGER NOT NULL,
                Day         INTEGER NOT NULL,
                MessageId   TEXT    NOT NULL UNIQUE,
                CreatedAt   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
