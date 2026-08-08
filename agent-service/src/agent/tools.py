from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def get_current_date() -> dict:
    """Return today's date in the formats used by the Budget Tracker API."""
    today = datetime.now(timezone.utc).date()
    return {
        "date": today.strftime("%Y-%m-%d"),
        "month_year": today.strftime("%m/%y"),
        "month": today.month,
        "year": today.year,
        "day": today.day,
    }
