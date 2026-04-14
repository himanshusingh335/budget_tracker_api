# Budget Tracker API

A FastAPI REST API for tracking monthly budgets and transactions, backed by SQLite.

---

## Prerequisites

- Python 3.13+
- [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/)
- Docker Hub account (only needed if you want to push images)

---

## Local Setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Database Initialisation

```bash
python import_data.py
```

This creates `data/budget.db` from the CSV seed files. Only needed on first run or after a DB reset.

---

## Run Locally

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8502
```

Or without activating the environment:

```bash
.venv/bin/uvicorn app.main:app --reload --port 8502
```

> Note: Do not run `python app/main.py` directly — use `uvicorn` or `python -m app.main` from the project root.

- API base: http://localhost:8502
- Swagger UI: http://localhost:8502/docs
- ReDoc: http://localhost:8502/redoc

---

## Testing the API

**Health check**
```bash
curl http://localhost:8502/
```

**Get budget summary for a month**
```bash
curl http://localhost:8502/summary/1/2025
```

**Get budget allocations for a month**
```bash
curl http://localhost:8502/budget/1/2025
```

**Add a budget allocation**
```bash
curl -X POST http://localhost:8502/budget \
  -H "Content-Type: application/json" \
  -d '{"MonthYear": "01/25", "Category": "Groceries", "Budget": 5000}'
```

**Add a transaction**
```bash
curl -X POST http://localhost:8502/transactions \
  -H "Content-Type: application/json" \
  -d '{"Date": "2025-01-15", "Description": "Supermarket", "Category": "Groceries", "Expenditure": 1200, "Year": 2025, "Month": 1, "Day": 15}'
```

**Partial update a transaction**
```bash
curl -X PATCH http://localhost:8502/transactions/42 \
  -H "Content-Type: application/json" \
  -d '{"Expenditure": 1350}'
```

---

## Docker — Build & Push

Make the script executable, then run it:

```bash
chmod +x docker_push.sh
./docker_push.sh              # builds and pushes as :latest
./docker_push.sh v1.0.0       # builds and pushes with a custom tag
```

This builds both the API and dashboard images and pushes them to Docker Hub. Requires `docker login` beforehand.

---

## Run in Container

A single `docker-compose.yml` handles both local builds and production pulls.

**Build and run from local source:**

```bash
docker compose up --build
```

**Pull and run the production images from Docker Hub:**

```bash
docker compose up -d
```

- API: http://localhost:8502
- Dashboard: http://localhost:8090

Transaction and budget data is persisted in a named Docker volume (`budget_data`).

---

## Project Structure

```
budget_tracker_api/
├── app/
│   ├── main.py              # FastAPI app, mounts all routers
│   ├── config.py            # DB path and app constants
│   ├── database.py          # get_db() dependency (SQLite connection)
│   ├── models/
│   │   ├── budget.py        # Pydantic schemas for budget endpoints
│   │   └── transaction.py   # Pydantic schemas for transaction endpoints
│   └── routers/
│       ├── budget.py        # /budget endpoints
│       ├── transactions.py  # /transactions endpoints
│       └── summary.py       # /summary endpoint
├── data/
│   └── budget.db            # SQLite database (git-ignored)
├── import_data.py           # Seed DB from CSV files
├── export_data_to_csv.py    # Export DB tables to CSV
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .mcp.json                # MCP server config (SSE endpoint on Pi)
└── docker_push.sh
```
