# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run locally
python app.py                     # Starts Flask on port 8502

# Initialize database from CSV seed files
python import_data.py             # Creates schema and imports budget_set.csv + budget_tracker.csv

# Export database tables to CSV
python export_data_to_csv.py      # Writes to csv_exports/

# Docker
docker build -t budget-tracker-api .
docker run -d -p 8502:8502 -v budget_data:/app/data --name budget_tracker_api budget-tracker-api
```

There is no test suite currently.

## Architecture

Single-file Flask REST API (`app.py`) backed by SQLite (`data/budget.db`).

**Database pattern:** `get_db_connection()` factory opens a connection with `row_factory = sqlite3.Row` for dict-like access. Connections are opened and closed manually per request.

**Two tables:**

- `budget_set` — monthly budget allocations: `id, MonthYear (TEXT "MM/YY"), Category, Budget (REAL)`
- `budget_tracker` — transactions: `id, Date, Description, Category, Expenditure (REAL), Year, Month, Day`

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/summary/<month>/<year>` | Budget vs actual per category |
| GET | `/budget/<month>/<year>` | Budget allocations for a month |
| GET | `/transactions/<month>/<year>` | Transactions for a month |
| POST | `/budget` | Add budget allocation |
| POST | `/transactions` | Record a transaction |
| DELETE | `/budget` | Delete budget by MonthYear+Category |
| DELETE | `/transactions/<id>` | Delete transaction by id |

`format_currency()` utility formats values as INR (₹). Month/year params are integers; `MonthYear` stored as `"MM/YY"` string.

## Dependencies

Only `flask` is required for the API. `pandas` is needed for `export_data_to_csv.py`. No requirements.txt exists — install manually.
