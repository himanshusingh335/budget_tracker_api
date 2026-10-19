import logging
import sqlite3
from datetime import date
from typing import Annotated, Optional, Union

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models.email_transaction import EmailTransactionCreate

# Deliberately NOT exposed over MCP: rows are written only by the email-ingest
# cron job (nginx blocks non-GET requests to this prefix from outside).
router = APIRouter(prefix="/email-transactions", tags=["Email Transactions"])
logger = logging.getLogger("budget-api")

COLUMNS = ("Date", "Description", "Type", "Amount", "Account", "Year", "Month", "Day", "MessageId")


def _datekey(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


@router.get("")
def get_email_transactions(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    start: Optional[date] = None,
    end: Optional[date] = None,
):
    """Return bank transactions parsed from emails, optionally filtered to an inclusive date range.

    Args:
        start: Earliest date to include (YYYY-MM-DD)
        end: Latest date to include (YYYY-MM-DD)
    """
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="start must be on or before end")
    datekey = "(Year * 10000 + Month * 100 + Day)"
    clauses, params = [], []
    if start:
        clauses.append(f"{datekey} >= ?")
        params.append(_datekey(start))
    if end:
        clauses.append(f"{datekey} <= ?")
        params.append(_datekey(end))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(
        f"SELECT * FROM email_transactions {where} ORDER BY {datekey} DESC, id DESC", params
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def add_email_transactions(
    payload: Union[EmailTransactionCreate, list[EmailTransactionCreate]],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
):
    """Insert one or more email-sourced transactions. Rows whose MessageId already exists are skipped."""
    items = payload if isinstance(payload, list) else [payload]
    inserted = 0
    for item in items:
        cur = db.execute(
            f"INSERT OR IGNORE INTO email_transactions ({', '.join(COLUMNS)}) "
            f"VALUES ({', '.join('?' * len(COLUMNS))})",
            tuple(getattr(item, c) for c in COLUMNS),
        )
        inserted += cur.rowcount
    db.commit()
    skipped = len(items) - inserted
    logger.info("add_email_transactions: inserted=%d skipped=%d", inserted, skipped)
    return {"inserted": inserted, "skipped": skipped}
