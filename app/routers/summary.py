import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models.budget import SummaryRow

router = APIRouter(prefix="/summary", tags=["Summary"])


def format_currency(value: float) -> str:
    return f"₹ {value:.2f}"


@router.get("/{month}/{year}", response_model=list[SummaryRow])
def get_summary(month: int, year: int, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Return a budget vs actual spending summary per category for a given month and year. Includes totals row. Amounts are formatted in INR (₹)."""
    month_year = f"{month:02d}/{str(year)[-2:]}"

    budget_cursor = db.execute(
        "SELECT Category, Budget FROM budget_set WHERE MonthYear = ?", (month_year,)
    )
    budget_data = {row["Category"]: row["Budget"] for row in budget_cursor.fetchall()}

    exp_cursor = db.execute(
        "SELECT Category, SUM(Expenditure) as Total FROM budget_tracker WHERE Month = ? AND Year = ? GROUP BY Category",
        (month, year),
    )
    exp_data = {row["Category"]: row["Total"] for row in exp_cursor.fetchall()}

    if not budget_data:
        raise HTTPException(status_code=404, detail="No budget data found for this month")

    summary = []
    total_budget = 0.0
    total_expense = 0.0

    for category in sorted(set(budget_data.keys()).union(exp_data.keys())):
        budget = budget_data.get(category, 0)
        expense = exp_data.get(category, 0)
        diff = budget - expense
        total_budget += budget
        total_expense += expense
        summary.append(SummaryRow(
            MonthYear=month_year,
            Category=category,
            Budget=format_currency(budget),
            Expenditure=format_currency(expense),
            Difference=format_currency(diff),
        ))

    summary.append(SummaryRow(
        MonthYear="Total",
        Category="",
        Budget=format_currency(total_budget),
        Expenditure=format_currency(total_expense),
        Difference=format_currency(total_budget - total_expense),
    ))

    return summary
