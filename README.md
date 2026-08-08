# Budget Tracker

A personal budget tracker split into four independently deployed services, wired together by `docker-compose.yml` and reverse-proxied by nginx.

## Services

- **backend-service** (FastAPI, port `8502`) — owns the SQLite database (`data/budget.db`, tables `budget_set` and `budget_tracker`). Exposes REST routes under `/summary`, `/budget`, `/transactions`, `/query`, and `/classify`, and also mounts an MCP server at `/mcp` (via `fastapi-mcp`) so its routes can be called as tools.
- **agent-service** (FastAPI + LangGraph, port `8000`) — "Penny", a Groq-backed LangChain agent that consumes backend-service's tools over MCP. Conversation state is checkpointed to Postgres. Data-mutating tools (adding/updating/deleting transactions or budgets) require human-in-the-loop confirmation; read-only tools do not.
- **frontend-service** — the static `app.html` UI, served by nginx.
- **nginx** — reverse proxy that routes `/chat/*` → agent-service, `/summary|budget|transactions|query|classify|mcp|docs|redoc|openapi.json` → backend-service, and everything else → frontend-service (see `nginx/nginx.conf`).

## Running locally (backend-service + agent-service)

All services (and the root scripts `import_data.py`, `export_data_to_csv.py`) share a single root `.venv` (a conda env) — there is no per-service virtualenv.

```bash
conda activate /Users/himanshusingh/Developer/budget-tracker/budget_tracker_api/.venv
```

### backend-service

```bash
cd backend-service
pip install -r requirements.txt
python app/main.py
```

Runs at **http://localhost:8502**, backed by the SQLite DB at `backend-service/data/budget.db`. Interactive API docs are at http://localhost:8502/docs, and the MCP server is mounted at http://localhost:8502/mcp.

### agent-service

agent-service requires a reachable Postgres instance (for LangGraph checkpointing) and a Groq API key.

```bash
cd agent-service
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:
- `GROQ_API_KEY` — required.
- `DATABASE_URL` — pointing at a running Postgres instance (e.g. `postgresql://postgres:postgres@localhost:5432/agent_service`). You can start just the Postgres container from the compose file: `docker compose up -d postgres`.
- `MCP_CONFIG_PATH=mcp_servers.local.json` — for local (non-docker) runs, so the agent reaches backend-service at `http://localhost:8502/mcp` instead of the docker-network hostname used by `mcp_servers.json`.

Then start it:

```bash
python src/main.py
```

Runs at **http://localhost:8000** by default (configurable via `PORT` in `.env`). With both services running locally, backend-service must already be up so the agent can connect over MCP.

## Running the entire app end-to-end with Docker

The full stack (frontend, backend, agent, Postgres, nginx) is defined in `docker-compose.yml`. From the repo root:

```bash
export GROQ_API_KEY=your_key_here   # required by agent-service
docker compose up --build
```

This builds and starts all five containers and exposes the whole app through nginx at **http://localhost:8502** — that's the only port exposed to the host; frontend-service, backend-service, agent-service, and Postgres are only reachable from each other over the internal `budget-network` Docker network (Postgres is additionally published on `localhost:5432` for convenience). Backend data persists in the external `budget_data` volume and agent checkpoints persist in `agent_postgres_data`.

| Service | URL |
| --- | --- |
| Whole app (via nginx) | http://localhost:8502 |
| → frontend (UI) | http://localhost:8502/ |
| → agent chat | http://localhost:8502/chat |
| → backend API/MCP | http://localhost:8502/summary, /budget, /transactions, /query, /classify, /mcp, /docs |
| Postgres (host access) | localhost:5432 |

To push built images to Docker Hub (used for deploying to the Raspberry Pi): `./docker_push.sh <tag>`.
