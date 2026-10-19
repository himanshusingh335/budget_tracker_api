"""Pull recent bank alert emails from Gmail, extract transactions with an LLM, POST them to backend-service.

Runs once and exits (scheduled by host cron). Re-running over overlapping windows is safe: the backend
dedupes on the email's Message-ID.
"""
import email
import email.header
import imaplib
import logging
import os
import re
import sys
from datetime import date, datetime, timedelta
from email.message import Message
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Literal, Optional
from zoneinfo import ZoneInfo

import httpx
from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
# httpx logs every request at INFO, which would bury the job's own summary lines.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("email-ingest")

IST = ZoneInfo("Asia/Kolkata")
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "2"))
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8502").rstrip("/")
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "google/gemini-2.5-flash")
MAX_BODY_CHARS = 4000

# Same coverage as the old Hermes digest: every HDFC sender, plus any "Credit Card" subject as a safety net.
# Monthly SmartStatements are excluded up front; anything else non-transactional is rejected by the LLM.
GMAIL_QUERIES = [
    f"from:hdfcbank -from:hdfcbanksmartstatement newer_than:{LOOKBACK_DAYS}d",
    f'subject:"Credit Card" newer_than:{LOOKBACK_DAYS}d',
]

SYSTEM_PROMPT = """You extract a single bank transaction from an Indian bank alert email.

Rules:
- If the email is not a completed debit/credit of money (e.g. statements, T&C/consent notices, OTPs,
  security/login alerts, payment-due reminders, offers, declined transactions), set is_transaction=false
  and leave the other fields empty.
- amount: positive number in rupees, no sign. direction: "debit" if money left the customer, "credit" if
  money came in (refunds, reversals and incoming transfers are credits).
- type: "UPI" for any UPI transaction — including UPI paid via a RuPay Credit Card; "Credit Card" for card
  swipes/online card payments; "Debit Card" for debit card or ATM use; "Net Banking" for NEFT/IMPS/RTGS/
  net banking transfers; otherwise "Other".
- description: the merchant or counterparty, as a human would name it. Prefer the readable name in
  parentheses over a masked VPA (e.g. "VPA ****2648@ptybl (DroptheQ)" -> "DroptheQ"). If only a VPA is
  given, use the VPA. Strip prefixes like "PAY*" only when the rest is clearly the merchant name.
- account_last4: last 4 digits of the card or account the money moved through, if stated.
- txn_date: the transaction date stated in the email body, as YYYY-MM-DD. Leave empty if not stated."""


class ExtractedTxn(BaseModel):
    is_transaction: bool = Field(description="False for anything that is not a completed money movement")
    amount: Optional[float] = Field(None, description="Absolute amount in rupees")
    direction: Optional[Literal["debit", "credit"]] = None
    type: Optional[Literal["UPI", "Credit Card", "Debit Card", "Net Banking", "Other"]] = None
    description: Optional[str] = None
    account_last4: Optional[str] = None
    txn_date: Optional[date] = None


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _decode(part: Message) -> str:
    payload = part.get_payload(decode=True) or b""
    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def body_text(msg: Message) -> str:
    plain, html = None, None
    for part in msg.walk():
        ctype = part.get_content_type()
        if part.get_content_disposition() == "attachment":
            continue
        if ctype == "text/plain" and plain is None:
            plain = _decode(part)
        elif ctype == "text/html" and html is None:
            html = _decode(part)
    if plain and plain.strip():
        text = plain
    elif html:
        parser = _TextExtractor()
        parser.feed(html)
        text = " ".join(parser.parts)
    else:
        text = ""
    text = re.sub(r"https?://\S+|\[\]\([^)]*\)", "", text)  # tracking links are pure token noise
    return re.sub(r"\s+", " ", text).strip()[:MAX_BODY_CHARS]


def fetch_messages(user: str, password: str) -> list[Message]:
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        imap.login(user, password)
        # All Mail so archived alerts are still found; readonly=True (EXAMINE) never touches \Seen flags.
        status, _ = imap.select('"[Gmail]/All Mail"', readonly=True)
        if status != "OK":
            imap.select("INBOX", readonly=True)
        uids: set[bytes] = set()
        for query in GMAIL_QUERIES:
            status, data = imap.uid("SEARCH", "X-GM-RAW", f'"{query.replace(chr(34), chr(92) + chr(34))}"')
            if status != "OK":
                raise RuntimeError(f"IMAP search failed for {query!r}: {data}")
            uids.update(data[0].split())
        logger.info("Found %d candidate emails", len(uids))
        messages = []
        for uid in sorted(uids, key=int):
            status, data = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            if status != "OK" or not data or not isinstance(data[0], tuple):
                logger.warning("Could not fetch UID %s", uid.decode())
                continue
            messages.append(email.message_from_bytes(data[0][1]))
        return messages
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def to_row(msg: Message, txn: ExtractedTxn) -> dict:
    received = parsedate_to_datetime(msg["Date"]).astimezone(IST).date() if msg["Date"] else datetime.now(IST).date()
    # Trust the body's date only if it's plausible relative to when the alert arrived.
    d = txn.txn_date if txn.txn_date and abs((received - txn.txn_date).days) <= 7 else received
    return {
        "Date": d.strftime("%d/%m/%y"),
        "Description": (txn.description or "Unknown").strip(),
        "Type": txn.type or "Other",
        "Amount": round(-txn.amount if txn.direction == "debit" else txn.amount, 2),
        "Account": txn.account_last4,
        "Year": d.year,
        "Month": d.month,
        "Day": d.day,
        "MessageId": msg["Message-ID"].strip(),
    }


def main() -> int:
    user, password = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    llm = ChatOpenRouter(
        model=EXTRACT_MODEL, api_key=os.environ["OPENROUTER_API_KEY"], temperature=0
    ).with_structured_output(ExtractedTxn)

    rows, failures = [], 0
    for msg in fetch_messages(user, password):
        subject = str(email.header.make_header(email.header.decode_header(msg["Subject"] or "")))
        if not msg["Message-ID"]:
            logger.warning("Skipping email without Message-ID: %s", subject)
            continue
        try:
            txn: ExtractedTxn = llm.invoke(
                [("system", SYSTEM_PROMPT), ("human", f"From: {msg['From']}\nSubject: {subject}\n\n{body_text(msg)}")]
            )
        except Exception:
            failures += 1
            logger.exception("Extraction failed for %s", subject)
            continue
        if not txn.is_transaction or not txn.amount or not txn.direction:
            logger.info("Not a transaction: %s", subject)
            continue
        row = to_row(msg, txn)
        logger.info("Extracted %s %s ₹%.2f %s", row["Date"], row["Type"], row["Amount"], row["Description"])
        rows.append(row)

    if rows:
        resp = httpx.post(f"{BACKEND_URL}/email-transactions", json=rows, timeout=30)
        resp.raise_for_status()
        logger.info("Backend: %s", resp.json())
    else:
        logger.info("No transactions to post")

    if failures:
        logger.error("%d email(s) failed extraction; they will be retried on the next run", failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
