# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run locally (FastAPI with uvicorn, hot-reload)
conda run -n flask-test uvicorn app.main:app --reload --port 8502

# Install FastAPI (one-time)
conda run -n flask-test pip install fastapi

# Initialize database from CSV seed files (unchanged)
conda run -n flask-test python import_data.py

# Export database tables to CSV (unchanged)
conda run -n flask-test python export_data_to_csv.py

# Docker
docker build -t budget-tracker-api .
docker run -d -p 8502:8502 -v budget_data:/app/data --name budget_tracker_api budget-tracker-api
```

There is no test suite currently.

## Architecture

FastAPI REST API (`app/`) backed by SQLite (`data/budget.db`), served by uvicorn.

```
app/
├── __init__.py
├── main.py              # FastAPI app, mounts all routers
├── config.py            # DB path and app constants
├── database.py          # get_db() dependency injection (generator)
├── models/
│   ├── budget.py        # Pydantic schemas: BudgetCreate, BudgetResponse, BudgetDeleteRequest, SummaryRow
│   └── transaction.py   # Pydantic schemas: TransactionCreate, TransactionResponse
└── routers/
    ├── budget.py        # /budget endpoints + /budget/export/csv
    ├── transactions.py  # /transactions endpoints + /transactions/export/csv
    └── summary.py       # /summary endpoint
```

**Database pattern:** `get_db()` generator in `app/database.py` opens a connection with `row_factory = sqlite3.Row` and closes it unconditionally via `finally`. Injected into routes via `Depends(get_db)`.

**Two tables:**

- `budget_set` — monthly budget allocations: `id, MonthYear (TEXT "MM/YY"), Category, Budget (REAL)`
- `budget_tracker` — transactions: `id, Date, Description, Category, Expenditure (REAL), Year, Month, Day`

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/summary/{month}/{year}` | Budget vs actual per category (INR formatted) |
| GET | `/budget/{month}/{year}` | Budget allocations for a month |
| POST | `/budget` | Add budget allocation |
| DELETE | `/budget` | Delete budget by MonthYear+Category (body) |
| GET | `/budget/export/csv` | Download full budget_set as CSV |
| GET | `/transactions/{month}/{year}` | Transactions for a month |
| POST | `/transactions` | Record a transaction |
| DELETE | `/transactions/{id}` | Delete transaction by id |
| GET | `/transactions/export/csv` | Download full budget_tracker as CSV |
| GET | `/docs` | Swagger UI (auto-generated) |
| GET | `/redoc` | ReDoc (auto-generated) |

`format_currency()` in `summary.py` formats values as INR (₹). Month/year params are integers; `MonthYear` stored as `"MM/YY"` string.

**Router ordering note:** In each router file, static paths (`/export/csv`) are registered **before** parameterised paths (`/{month}/{year}`, `/{id}`) to prevent FastAPI treating "export" as an integer.

## Dependencies

See `requirements.txt`: `fastapi`, `uvicorn`, `pydantic`, `pandas` (for `export_data_to_csv.py`).
