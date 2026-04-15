import csv
import io
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.database import get_db
from app.models.transaction import TransactionCreate, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["Transactions"])


# Static path MUST be registered before parameterized path /{id}
@router.get("/export/csv")
def export_transactions_csv(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Download the full budget_tracker table as a CSV file.

    Returns all transactions across all months as a downloadable CSV attachment.
    """
    rows = db.execute(
        "SELECT id, Date, Description, Category, Expenditure, Year, Month, Day FROM budget_tracker"
    ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "Date", "Description", "Category", "Expenditure", "Year", "Month", "Day"])
    writer.writerows([tuple(r) for r in rows])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=budget_tracker.csv"},
    )


@router.get("/{month}/{year}")
def get_transactions(month: int, year: int, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Return all transactions (expenditures) for a given month and year.

    Args:
        month: Month number (1-12)
        year: Full year, e.g. 2025
    """
    rows = db.execute(
        "SELECT * FROM budget_tracker WHERE Month = ? AND Year = ?", (month, year)
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def add_transaction(payload: TransactionCreate, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Record a new transaction (expenditure).

    Args:
        payload: Transaction details including Date (DD/MM/YYYY), Description, Category, Expenditure amount, and Year/Month/Day as integers
    """
    db.execute(
        "INSERT INTO budget_tracker (Date, Description, Category, Expenditure, Year, Month, Day) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (payload.Date, payload.Description, payload.Category, payload.Expenditure,
         payload.Year, payload.Month, payload.Day),
    )
    db.commit()
    return {"message": "Expenditure added successfully"}


@router.patch("/{id}", status_code=200)
def update_transaction(id: int, payload: TransactionUpdate, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Partially update a transaction by its ID.

    Args:
        id: Integer ID of the transaction to update
        payload: Fields to update — any subset of Date, Description, Category, Expenditure, Year, Month, Day
    """
    fields = payload.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    existing = db.execute("SELECT id FROM budget_tracker WHERE id = ?", (id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Transaction not found")

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    db.execute(
        f"UPDATE budget_tracker SET {set_clause} WHERE id = ?",
        (*fields.values(), id),
    )
    db.commit()
    row = db.execute("SELECT * FROM budget_tracker WHERE id = ?", (id,)).fetchone()
    return dict(row)


@router.delete("/{id}", status_code=200)
def delete_transaction(id: int, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Delete a transaction by its ID.

    Args:
        id: Integer ID of the transaction to delete
    """
    db.execute("DELETE FROM budget_tracker WHERE id = ?", (id,))
    db.commit()
    return {"message": "Expenditure deleted successfully"}
