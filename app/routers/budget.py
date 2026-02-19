import csv
import io
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..database import get_db
from ..models.budget import BudgetCreate, BudgetDeleteRequest

router = APIRouter(prefix="/budget", tags=["Budget"])


# Static path MUST be registered before parameterized path /{month}/{year}
@router.get("/export/csv")
def export_budget_csv(db: Annotated[sqlite3.Connection, Depends(get_db)]):
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
    month_year = f"{month:02d}/{str(year)[-2:]}"
    rows = db.execute(
        "SELECT Category, Budget FROM budget_set WHERE MonthYear = ?", (month_year,)
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="No budget data found for this month")
    return {"MonthYear": month_year, "Budgets": [dict(r) for r in rows]}


@router.post("/", status_code=201)
def add_budget(payload: BudgetCreate, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    db.execute(
        "INSERT INTO budget_set (MonthYear, Category, Budget) VALUES (?, ?, ?)",
        (payload.MonthYear, payload.Category, payload.Budget),
    )
    db.commit()
    return {"message": "Budget entry added successfully"}


@router.delete("/", status_code=200)
def delete_budget(payload: BudgetDeleteRequest, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    db.execute(
        "DELETE FROM budget_set WHERE MonthYear = ? AND Category = ?",
        (payload.MonthYear, payload.Category),
    )
    db.commit()
    return {"message": "Budget entry deleted successfully"}
