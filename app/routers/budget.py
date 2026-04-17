import csv
import io
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.database import get_db
from app.models.budget import BudgetCreate

router = APIRouter(prefix="/budget", tags=["Budget"])


# Static path MUST be registered before parameterized path /{month}/{year}
@router.get("/export/csv")
def export_budget_csv(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Download the full budget_set table as a CSV file.

    Returns all budget allocations across all months as a downloadable CSV attachment.
    """
    rows = db.execute("SELECT id, MonthYear, Category, Budget FROM budget_set").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "MonthYear", "Category", "Budget"])
    writer.writerows([tuple(r) for r in rows])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=budget_set.csv"},
    )


@router.get("/{month}/{year}")
def get_budget(month: int, year: int, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Return budget allocations for each category for a given month and year.

    Args:
        month: Month number (1-12)
        year: Full year, e.g. 2025
    """
    month_year = f"{month:02d}/{str(year)[-2:]}"
    rows = db.execute(
        "SELECT Category, Budget FROM budget_set WHERE MonthYear = ?", (month_year,)
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="No budget data found for this month")
    return {"MonthYear": month_year, "Budgets": [dict(r) for r in rows]}


@router.post("", status_code=201)
def add_budget(payload: BudgetCreate, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Add a new budget allocation for a category and month.

    Args:
        payload: Budget details including MonthYear (MM/YY format, e.g. '04/25'), Category, and Budget amount
    """
    db.execute(
        "INSERT INTO budget_set (MonthYear, Category, Budget) VALUES (?, ?, ?)",
        (payload.MonthYear, payload.Category, payload.Budget),
    )
    db.commit()
    return {"message": "Budget entry added successfully"}


@router.delete("", status_code=200)
def delete_budget(
    MonthYear: Annotated[str, Query()],
    Category: Annotated[str, Query()],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
):
    """Delete a budget allocation for a specific category and month.

    Args:
        MonthYear: MM/YY format, e.g. '04/25'
        Category: Category name to delete
    """
    db.execute(
        "DELETE FROM budget_set WHERE MonthYear = ? AND Category = ?",
        (MonthYear, Category),
    )
    db.commit()
    return {"message": "Budget entry deleted successfully"}
