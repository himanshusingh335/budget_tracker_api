import logging
import sqlite3
from datetime import date
from typing import Annotated, Optional, Union

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models.email_transaction import EmailTransactionCreate

# GET is exposed over MCP (read-only, for Penny). POST is deliberately not: rows are
# written only by the email-ingest cron job (nginx blocks non-GET requests from outside).
router = APIRouter(prefix="/email-transactions", tags=["Email Transactions"])
logger = logging.getLogger("budget-api")

COLUMNS = ("Date", "Description", "Type", "Amount", "Account", "Year", "Month", "Day", "MessageId")


def _datekey(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


@router.get("", operation_id="get_email_transactions")
def get_email_transactions(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    start: Optional[date] = None,
    end: Optional[date] = None,
):
    """RECONCILIATION ONLY: return the transactions the user's bank (HDFC) reported in its alert emails.

    Only call this when the user wants to check their logged expenses against the bank, for example
    "which transactions am I missing?", "what haven't I logged?", or "do my transactions tally with my
    bank/email statements?". For every other question (spending, totals, categories, budgets) use
    get_transactions, get_summary or run_query on budget_tracker instead, and do not call this tool.

    How it differs from get_transactions: get_transactions is the expenses the user logged themselves
    (with categories; budgets are measured against these). This tool is what the bank actually
    recorded: every UPI payment, card swipe and bank transfer, plus money received. It has no
    categories, is imported once a day (so it can lag by up to a day), and the same purchase usually
    appears in BOTH sources, so never add the two together.

    To reconcile: fetch both sources for the same date range, then match each bank debit (negative
    Amount) to a logged expense with the same amount and a date within about 2 days. Unmatched bank
    debits are likely expenses the user forgot to log. Logged expenses with no bank match may be cash
    or another bank. Ignore credits (positive Amount) and transfers to the user's own accounts unless
    asked.

    Args:
        start: Earliest date to include, inclusive, ISO format YYYY-MM-DD (e.g. "2026-10-01").
        end: Latest date to include, inclusive, ISO format YYYY-MM-DD (e.g. "2026-10-31").
            For a whole month pass the first and last day of that month. Both are optional, but
            always pass them: omitting both returns the entire history.

    Returns:
        A list of rows, newest first, each with:
          Date        "DD/MM/YY"
          Description merchant or counterparty; sometimes only a UPI ID like "payu@mairtel"
          Type        "UPI" | "Credit Card" | "Debit Card" | "Net Banking" | "Other"
          Amount      signed rupees: NEGATIVE = money spent/sent (debit), POSITIVE = money received (credit)
          Account     last 4 digits of the card or account used, or null
          Year, Month, Day, id, MessageId, CreatedAt   bookkeeping fields, rarely useful to show
        An empty list means no bank alerts in that range, not an error.
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
