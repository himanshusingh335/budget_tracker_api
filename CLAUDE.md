# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This is a personal budget tracker split into four independently deployed services, wired together by `docker-compose.yml` and reverse-proxied by nginx:

- **backend-service** (FastAPI, port 8502) — owns the SQLite database (`data/budget.db`, tables `budget_set` and `budget_tracker`). Exposes REST routes under `/summary`, `/budget`, `/transactions`, `/query`, `/classify`, and also mounts an MCP server at `/mcp` via `fastapi-mcp` (see `app/main.py`). Every FastAPI route that should be callable as an MCP tool must be explicitly listed in the `FastApiMCP(include_operations=[...])` call in `app/main.py`, matching the route's `operation_id`.
- **agent-service** (FastAPI + LangGraph, port 8000) — "Penny", an OpenRouter-backed LangChain agent (`src/agent/graph.py`) that consumes backend-service's tools over MCP (`src/agent/mcp.py`, configured via `mcp_servers.json`/`mcp_servers.local.json`). Conversation state is checkpointed to Postgres (`src/agent/checkpointer.py`, `langgraph-checkpoint-postgres`). All data-mutating tools (`add_transaction`, `update_transaction`, `delete_transaction`, `add_budget`, `delete_budget`) are gated behind `HumanInTheLoopMiddleware` in `src/agent/middleware.py` — read-only tools are not. The system prompt in `graph.py` enforces response formatting (₹ currency, Indian-style digit grouping, HTML tables only, one sentence of prose).
- **frontend-service** — static `app.html` served by nginx.
- **nginx** — routes `/chat/*` → agent-service, `/summary|budget|transactions|query|classify|mcp|docs|redoc|openapi.json` → backend-service, everything else → frontend-service. See `nginx/nginx.conf` for the exact regex.

Query flow for the agent: user message → agent-service → MCP tool call → backend-service route → SQLite. `query.py`'s `run_query` tool is the general-purpose escape hatch for cross-month/aggregation questions that the single-month `get_summary`/`get_budget`/`get_transactions` endpoints can't answer; it only permits `SELECT` statements (rejects any non-SELECT first token).

Transaction categorization: `classify.py` lazily loads a `sentence-transformers` embedder plus a pre-trained `LinearSVC` (`models/classifier.joblib`, `models/label_encoder.joblib`) to predict one of a fixed category set from free-text descriptions. The agent's system prompt instructs it to call `classify_description` automatically when a transaction is added without an explicit category.

Money formats to preserve when touching agent/formatting code: `MonthYear` is always `MM/YY` (e.g. `04/25`); transaction `Date` is `DD/MM/YY`; currency is always ₹ with Indian-style grouping (₹1,23,456.00), never "INR"/"Rs".

## Running services locally

All services (and the ad-hoc root scripts `import_data.py`, `export_data_to_csv.py`) share the single root `.venv` (a conda env) — there is no per-service virtualenv. Activate it before running anything:

```bash
conda activate /Users/himanshusingh/Developer/budget-tracker/budget_tracker_api/.venv

# backend-service (from backend-service/)
pip install -r requirements.txt
python app/main.py

# agent-service (from agent-service/)
pip install -r requirements.txt
cp .env.example .env   # set OPENROUTER_API_KEY; for local (non-docker) runs set
                        # MCP_CONFIG_PATH=mcp_servers.local.json to hit http://localhost:8502/mcp
python src/main.py
```

agent-service requires a reachable Postgres (`DATABASE_URL`) for checkpointing — `docker-compose.yml` provides one, or point at a local instance.

Full stack: `docker compose up --build` (nginx on `:8502`). `docker_push.sh <tag>` builds and pushes all four service images to Docker Hub (`mariox1105/budget-tracker-{backend,frontend,agent,nginx}`) — this is used for deploying to the Raspberry Pi.

## Data scripts

`import_data.py` / `export_data_to_csv.py` (root) move data between the SQLite DB and the CSV files in `csv_exports/`; both operate on `backend-service/data/budget.db` by path, not through the API.
