import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_db

router = APIRouter(prefix="/query", tags=["Query"])

SCHEMA = """
Tables:

  budget_set
    - id          INTEGER  PRIMARY KEY
    - MonthYear   TEXT     Budget month in "MM/YY" format (e.g. "01/25" for Jan 2025)
    - Category    TEXT     Spending category name (e.g. "Groceries", "Dining", "Rent")
    - Budget      REAL     Allocated budget amount in INR

  budget_tracker
    - id          INTEGER  PRIMARY KEY
    - Date        TEXT     Transaction date as "DD/MM/YYYY"
    - Description TEXT     Free-text description of the transaction
    - Category    TEXT     Spending category (matches categories in budget_set)
    - Expenditure REAL     Amount spent in INR
    - Year        INTEGER  4-digit year (e.g. 2025)
    - Month       INTEGER  Month number 1-12
    - Day         INTEGER  Day of month 1-31
"""


class QueryRequest(BaseModel):
    sql: str


@router.post("")
def run_query(payload: QueryRequest, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Execute a read-only SQL SELECT query against the budget database and return results as a list of objects.

    Use this tool when you need to answer questions that require cross-month analysis,
    aggregations, trends, filtering, or any query that the single-month lookup tools
    cannot satisfy on their own.

    Database schema:

      budget_set
        - id          INTEGER  PRIMARY KEY
        - MonthYear   TEXT     Budget month in "MM/YY" format (e.g. "01/25" for Jan 2025)
        - Category    TEXT     Spending category name (e.g. "Groceries", "Dining", "Rent")
        - Budget      REAL     Allocated budget amount in INR

      budget_tracker
        - id          INTEGER  PRIMARY KEY
        - Date        TEXT     Transaction date as "DD/MM/YYYY"
        - Description TEXT     Free-text description of the transaction
        - Category    TEXT     Spending category (matches categories in budget_set)
        - Expenditure REAL     Amount spent in INR
        - Year        INTEGER  4-digit year (e.g. 2025)
        - Month       INTEGER  Month number 1-12
        - Day         INTEGER  Day of month 1-31

    Example queries:

      -- Total spending per category for a full year
      SELECT Category, ROUND(SUM(Expenditure), 2) AS total
      FROM budget_tracker WHERE Year = 2025
      GROUP BY Category ORDER BY total DESC

      -- Monthly spending trend
      SELECT Month, ROUND(SUM(Expenditure), 2) AS total
      FROM budget_tracker WHERE Year = 2025
      GROUP BY Month ORDER BY Month

      -- Budget vs actual across all months in a year
      SELECT b.MonthYear, b.Category,
             b.Budget,
             COALESCE(SUM(t.Expenditure), 0) AS spent,
             ROUND(b.Budget - COALESCE(SUM(t.Expenditure), 0), 2) AS remaining
      FROM budget_set b
      LEFT JOIN budget_tracker t
        ON b.Category = t.Category
        AND b.MonthYear = printf('%02d/%02d', t.Month, t.Year % 100)
      WHERE b.MonthYear LIKE '%/25'
      GROUP BY b.MonthYear, b.Category
      ORDER BY b.MonthYear, b.Category

      -- Search transactions by description keyword
      SELECT * FROM budget_tracker
      WHERE Description LIKE '%Swiggy%'
      ORDER BY Year DESC, Month DESC, Day DESC

      -- Top 10 largest single transactions
      SELECT Date, Description, Category, Expenditure
      FROM budget_tracker
      ORDER BY Expenditure DESC LIMIT 10

      -- Months where spending exceeded budget for a category
      SELECT t.Month, t.Year, t.Category,
             ROUND(SUM(t.Expenditure), 2) AS spent, b.Budget
      FROM budget_tracker t
      JOIN budget_set b
        ON b.Category = t.Category
        AND b.MonthYear = printf('%02d/%02d', t.Month, t.Year % 100)
      WHERE t.Category = 'Groceries'
      GROUP BY t.Month, t.Year, t.Category
      HAVING spent > b.Budget

    Rules:
      - Only SELECT statements are permitted; INSERT, UPDATE, DELETE, DROP, and other
        data-modifying or DDL statements will be rejected.
      - Always use Year and Month integer columns for date filtering — do not parse the
        Date text column for range queries.
      - MonthYear in budget_set uses "MM/YY" format; join to budget_tracker using
        printf('%02d/%02d', Month, Year % 100) to align them.

    Args:
        payload: Object with a single "sql" field containing the SELECT statement to run.

    Returns:
        A list of row objects. Each object's keys are the column names from the query.
    """
    sql = payload.sql.strip()

    first_token = sql.split()[0].upper() if sql.split() else ""
    if first_token != "SELECT":
        raise HTTPException(
            status_code=400,
            detail="Only SELECT statements are permitted.",
        )

    try:
        rows = db.execute(sql).fetchall()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query error: {e}")

    return [dict(row) for row in rows]
