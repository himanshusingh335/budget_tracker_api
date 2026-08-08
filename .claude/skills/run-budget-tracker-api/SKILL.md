---
name: run-budget-tracker-api
description: Run, launch, drive, curl-test, or smoke-test budget-tracker-api's backend-service (FastAPI + SQLite) and agent-service (LangGraph "Penny" agent). Use when asked to start the API, test an endpoint, exercise the chat agent, or verify a backend/agent change actually works — not just that unit tests pass.
---

Paths below are relative to the repo root (`<unit>` = this repo,
`budget_tracker_api/`), not to this skill directory.

This project is four services wired by `docker-compose.yml`, but you rarely
need the whole stack to verify a change: **backend-service** is a
self-contained FastAPI + SQLite app you can run and curl directly, and
**agent-service** just needs backend-service's MCP endpoint + a Postgres URL.
The driver at `.claude/skills/run-budget-tracker-api/driver.sh` launches both
against **sandboxed copies of the data** (a throwaway `budget.db` copy and an
isolated Postgres database), so you can freely add/update/delete transactions
without touching the user's real financial data or the real chat checkpoint
history. It reuses the shared root `.venv` — no separate install step.

## Prerequisites

None beyond what's already in the repo: the root `.venv` conda env already
has every dependency for both services installed, `backend-service/data/budget.db`
already has real data to query, and `agent-service/.env` already has
`OPENROUTER_API_KEY` set. Postgres must be reachable at `localhost:5432` with
user/pass `postgres`/`postgres` — the project's own `docker-compose.yml`
stack (run via `docker compose up`) provides this; on this machine it's
already running in the background via OrbStack, so nothing extra is needed.

## Run (agent path — use this)

```bash
# Backend only (FastAPI + SQLite, sandboxed DB copy), on :8503
bash .claude/skills/run-budget-tracker-api/driver.sh up backend

# Also start agent-service on :8001, wired to the sandboxed backend's
# MCP endpoint and an isolated Postgres DB (agent_service_skilltest)
bash .claude/skills/run-budget-tracker-api/driver.sh up agent

# curl-based smoke test of backend-service (health, summary, classify,
# run_query, and a full add/patch/delete transaction round-trip)
bash .claude/skills/run-budget-tracker-api/driver.sh smoke

# Send a message to Penny (the LangGraph agent) and print the reply
bash .claude/skills/run-budget-tracker-api/driver.sh chat "What was my total spending in October 2023?" my-session

# A mutating request (add_transaction, update_transaction, delete_transaction,
# add_budget, delete_budget) pauses for human-in-the-loop approval instead of
# a reply — resolve it with:
bash .claude/skills/run-budget-tracker-api/driver.sh resume my-session approve   # or: reject

# Stop both services and drop the isolated Postgres DB
bash .claude/skills/run-budget-tracker-api/driver.sh down
```

Logs land in `.claude/skills/run-budget-tracker-api/.sandbox/{backend,agent}.log`.
Override ports with `BACKEND_PORT=... AGENT_PORT=...` env vars if 8503/8001
are taken.

### Direct invocation (no server) — for backend logic changes

Most backend-service PRs touch a single router function. You can hit it
without any server by importing the app and using FastAPI's `TestClient`,
still against the real `.venv`:

```bash
cd backend-service
../.venv/bin/python -c "
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
print(c.get('/summary/10/2023').json())
"
```

This uses whatever `data/budget.db` is on disk relative to CWD — run it from
a copied sandbox dir (like the driver does) if you're testing mutations.

## Run (human path)

```bash
conda activate ./.venv
cd backend-service && python app/main.py       # :8502, real data
cd agent-service && python src/main.py         # :8000, needs Postgres + OPENROUTER_API_KEY
```

Useless in a headless/CI context since both just block in the foreground;
prefer the driver above, which backgrounds them and gives you `curl`/chat
access.

## Full stack (all four services + nginx)

`docker compose up --build` — only needed when testing nginx routing or the
static frontend. Not exercised by this driver; the driver's backend/agent
combo covers the actual application logic.

## Test suite

No test suite exists in this repo (`find . -name 'test_*.py' -o -name '*_test.py'`
returns nothing outside `.venv`). The driver's `smoke` command and manual
`chat` calls are the verification path.

## Gotchas

- **`DB_PATH = "data/budget.db"` in `backend-service/app/config.py` is
  relative to CWD, not to the app package.** The driver runs uvicorn with
  `--app-dir backend-service` but `cd`s into the sandbox dir first, so the
  server picks up the sandboxed `data/budget.db` instead of the real one.
  If you invoke uvicorn yourself from `backend-service/`, you'll hit the
  real database — copy it elsewhere first if you're testing writes.
- **`models/` for the classifier is resolved relative to the app package**
  (`Path(__file__).parent.parent.parent / "models"` in `classify.py`), *not*
  CWD, so it keeps working correctly even when you `cd` elsewhere for the
  DB sandboxing above.
- **The `/mcp` endpoint is not curl-friendly.** It's a stateful
  streamable-HTTP MCP session (`POST /mcp` without a prior session ID
  returns `"Missing session ID"`). Don't try to smoke-test it with raw
  curl; drive it through agent-service (which spins up a proper MCP client
  session) or a real MCP client instead.
- **agent-service's `DATABASE_URL` in `.env` points at `agent_service`**,
  the same Postgres database the production `docker-compose` stack uses for
  real chat history checkpoints. The driver creates/uses a separate
  `agent_service_skilltest` database instead so test conversations never
  land in production checkpoint history — don't override `DATABASE_URL`
  back to `agent_service` unless you intend to touch real chat state.
- **Mutating tool calls always pause first.** `add_transaction`,
  `update_transaction`, `delete_transaction`, `add_budget`, `delete_budget`
  are gated by `HumanInTheLoopMiddleware` — `chat/invoke` returns
  `pending_actions` with `reply: null` instead of executing. You must call
  `chat/resume` with an `approve`/`reject` decision to continue.
- **bash quoting**: don't build the chat/resume JSON body with a Python
  `-c` one-liner that embeds a dict literal `{...}` directly inside a
  double-quoted `-d "$(...)"` — bash's word-splitting/brace handling mangles
  it. The driver passes values through env vars instead
  (`os.environ["DRIVER_MESSAGE"]`) to sidestep this; follow that pattern if
  you extend `driver.sh`.

## Troubleshooting

- `ERROR: [Errno 48] Address already in use` on backend startup — port 8502
  (or whatever `BACKEND_PORT` you chose) is already bound, usually by the
  production docker-compose stack. Use a different `BACKEND_PORT` (the
  driver defaults to 8503 for exactly this reason).
- Agent startup log shows `mcp.client.streamable_http` connection lines but
  then nothing — check `.sandbox/agent.log` for `loaded N MCP tool(s)`; if
  it's missing, backend-service isn't reachable yet at the URL in
  `mcp_servers.json` (start backend first, or let `up agent` do it
  automatically).
- `psycopg.OperationalError: connection failed` — Postgres isn't listening
  on `localhost:5432`. Start the project's stack (`docker compose up -d
  postgres`) or point at your own instance.
