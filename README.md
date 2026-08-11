# Budget Tracker

A personal budget tracker split into four independently deployed services, wired together by `docker-compose.yml` and reverse-proxied by nginx.

## Services

- **backend-service** (FastAPI, port `8502`) — owns the SQLite database (`data/budget.db`, tables `budget_set` and `budget_tracker`). Exposes REST routes under `/summary`, `/budget`, `/transactions`, `/query`, and `/classify`, and also mounts an MCP server at `/mcp` (via `fastapi-mcp`) so its routes can be called as tools.
- **agent-service** (FastAPI + LangGraph, port `8000`) — "Penny", an OpenRouter-backed LangChain agent that consumes backend-service's tools over MCP. Conversation state is checkpointed to Postgres. Data-mutating tools (adding/updating/deleting transactions or budgets) require human-in-the-loop confirmation; read-only tools do not.
- **frontend-service** — the static `app.html` UI, served by nginx.
- **nginx** — reverse proxy that routes `/chat/*` → agent-service, `/summary|budget|transactions|query|classify|mcp|docs|redoc|openapi.json` → backend-service, and everything else → frontend-service (see `nginx/nginx.conf`).

## Running locally (backend-service + agent-service)

All services (and the `db_backup/` scripts) share a single root `.venv` (a conda env) — there is no per-service virtualenv.

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

agent-service requires a reachable Postgres instance (for LangGraph checkpointing) and an OpenRouter API key.

```bash
cd agent-service
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:
- `OPENROUTER_API_KEY` — required.
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
export OPENROUTER_API_KEY=your_key_here   # required by agent-service
docker compose up --build
```

This builds and starts all five containers and exposes the whole app through nginx at **http://localhost:8502**; frontend-service, backend-service, agent-service, and Postgres are only reachable from each other over the internal `budget-network` Docker network (Postgres is additionally published on `localhost:5432` for convenience). Backend data persists in the external `budget_data` volume and agent checkpoints persist in `agent_postgres_data`.

| Service | URL |
| --- | --- |
| Whole app (via nginx) | http://localhost:8502 |
| → frontend (UI) | http://localhost:8502/ |
| → agent chat | http://localhost:8502/chat |
| → backend API/MCP | http://localhost:8502/summary, /budget, /transactions, /query, /classify, /mcp, /docs |
| Postgres (host access) | localhost:5432 |

To push built images to Docker Hub (used for deploying to the Raspberry Pi): `./docker_push.sh <tag>`.

## Production deployment (Raspberry Pi)

The Pi runs the same `docker-compose.yml` stack described above, pulling
pre-built images from Docker Hub instead of building locally. nginx is the
only container with a port published to the public internet.

```mermaid
flowchart LR
    user["Browser / Penny client"] -->|":8502"| nginx

    subgraph pi["Raspberry Pi — docker compose"]
        nginx["nginx"]
        frontend["frontend-service<br/>static app.html"]
        backend["backend-service<br/>FastAPI + MCP"]
        agent["agent-service<br/>LangGraph 'Penny'"]
        pg["postgres:16<br/>checkpoints"]
        vol[("budget_data volume<br/>budget.db")]

        nginx -->|"/ (default)"| frontend
        nginx -->|"/summary /budget /transactions<br/>/query /classify /mcp /docs"| backend
        nginx -->|"/chat/*"| agent
        agent -.->|"MCP tool calls"| backend
        backend --> vol
        agent --> pg
    end
```

Deploying is `bash .claude/skills/deploy-to-pi/deploy.sh`, which drives:

```mermaid
sequenceDiagram
    participant Dev as Dev machine
    participant Hub as Docker Hub
    participant Pi as Pi

    Dev->>Hub: 1. docker_push.sh — build + push 4 images
    Hub->>Pi: 2. docker compose pull && up -d (recreates only changed images)
    Note over Pi: 3. docker compose restart nginx — always, not conditional
    Pi-->>Dev: 4. curl /app and /chat/sessions — expect 200
```

**Why step 3 always runs:** `docker compose up -d` only recreates containers
whose image changed — e.g. a frontend-only deploy leaves `backend-service`
and `nginx` untouched. The recreated container gets a new internal Docker
IP, but nginx resolved its upstream hostnames to IPs once at its own
startup and won't re-resolve them, so every route 502s until nginx is
restarted — even though `docker compose ps` shows everything "Up".

## Pulling prod data down for local testing

`db_backup/` is **not** a disaster-recovery tool for the Pi — the Pi keeps
its own Docker volume and isn't restored via this repo. Instead it's for
pulling the latest prod data snapshot down locally so you can test new
features against real data.

- `backup_to_s3.sh` is a reference copy of the script that actually runs
  nightly via cron on the Pi (`~/budget-tracker/budget-api-db-backup.sh`) —
  it dumps `budget.db` out of the running `backend-service` container and
  uploads it to S3. It isn't meant to be run from a dev machine; keep the two
  copies in sync by hand if you change one.
- `restore_latest_backup.py` pulls the most recent S3 backup and restores it
  locally. Requires the `aws` CLI to already be authenticated
  (`aws login`), since it shells out to `aws s3`.

```mermaid
flowchart LR
    subgraph nightly["Nightly cron, on the Pi"]
        direction LR
        c1["backend-service<br/>container"] -->|"docker cp"| tmp["host /tmp"]
        tmp -->|"aws s3 cp"| s3[("s3://…-backups/<br/>backup_&lt;timestamp&gt;/budget.db")]
    end

    subgraph manual["Manual, on a dev machine"]
        direction RL
        s3b[("s3://…-backups/<br/>latest prefix")] -->|"aws s3 ls"| restore["restore_latest_backup.py"]
        restore --> dbfile["backend-service/data/budget.db"]
        restore --> sandbox[".sandbox db (if present)"]
        restore --> csv["csv_exports/ (regenerated)"]
    end
```

The restore path never writes back to the Pi — it's for pulling a
prod-shaped dataset down to test against locally, not for recovering the
Pi's own volume.

```bash
aws login   # if your session has expired
python db_backup/restore_latest_backup.py
```

This restores `backend-service/data/budget.db` (backing up whatever was
already there to `budget.db.bak-<timestamp>` first), also refreshes the
`run-budget-tracker-api` skill's sandboxed DB copy if present, and
regenerates CSVs into `db_backup/csv_exports/` for a quick human-readable
look at the data.

**If you're running the stack via `docker compose`**, this restore alone
has no effect on a running container: `backend-service/data` is mounted
from the named `budget_data` volume, which only ever seeds from the local
`data/` folder once, the first time the (empty) volume is created — after
that it's fully decoupled from the file on disk. To push a freshly
restored DB into an already-running container:

```bash
docker cp backend-service/data/budget.db $(docker compose ps -q backend-service):/app/data/budget.db
docker compose restart backend-service
```

## Retraining the transaction category classifier

`classifier-training/` retrains the model behind `/classify` (`classify_description`
in the MCP tool list) — the sentence-transformer + classifier pair that suggests
a category from a free-text transaction description. It reads the CSV export
produced by the data-pulling step above, so run that first if you want to train
on the latest prod data:

```mermaid
flowchart LR
    csv["db_backup/csv_exports/<br/>budget_tracker.csv"] -->|"train.py"| artifacts["backend-service/models/<br/>classifier.joblib + label_encoder.joblib"]
    artifacts -->|"docker build<br/>COPY models/"| image["backend-service image"]
    artifacts -.->|"test.py<br/>(local sanity check)"| dev["dev machine"]
```

```bash
python db_backup/restore_latest_backup.py   # optional — pulls the latest data first
python classifier-training/train.py         # retrains, overwrites backend-service/models/*.joblib
python classifier-training/test.py          # sanity-check predictions locally
```

Training is deterministic (fixed `RANDOM_STATE`), so re-running it against
unchanged data produces byte-identical model files — a no-op in `git diff`.
Retraining is manual only; there's no cron job for it. A running
`backend-service` caches the model in-process, so a locally running container
needs a restart (see `docker cp`/restart above, targeting
`backend-service/models/` instead of `data/`) and the Pi needs a redeploy
(`deploy-to-pi` skill) to pick up a newly trained model.
