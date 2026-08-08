#!/usr/bin/env bash
# Driver for running/driving budget-tracker-api services without touching
# the real data (backend-service/data/budget.db) or the real Postgres
# checkpoint DB used by the production docker-compose stack.
#
# Usage:
#   driver.sh up backend           # start backend-service on :8503 against a
#                                   # throwaway copy of budget.db
#   driver.sh up agent             # also start agent-service on :8001,
#                                   # wired to the sandboxed backend's MCP
#                                   # endpoint and an isolated Postgres DB
#                                   # (agent_service_skilltest)
#   driver.sh smoke                # curl-based smoke test of backend-service
#   driver.sh chat "<message>" [session_id]   # send a chat message to Penny
#   driver.sh resume <session_id> approve|reject   # resolve a pending action
#   driver.sh down                 # kill both services + drop the test DB
#
# Ports/paths are overridable via env: BACKEND_PORT (8503), AGENT_PORT (8001).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PY="$ROOT/.venv/bin/python"
SANDBOX="$ROOT/.claude/skills/run-budget-tracker-api/.sandbox"
BACKEND_PORT="${BACKEND_PORT:-8503}"
AGENT_PORT="${AGENT_PORT:-8001}"
PGDB="agent_service_skilltest"
PIDFILE="$SANDBOX/pids"

mkdir -p "$SANDBOX/data"

up_backend() {
  if [ ! -f "$SANDBOX/data/budget.db" ]; then
    cp "$ROOT/backend-service/data/budget.db" "$SANDBOX/data/budget.db"
  fi
  echo "Starting backend-service on :$BACKEND_PORT (sandboxed DB at $SANDBOX/data/budget.db)"
  (
    cd "$SANDBOX"
    nohup "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
      --app-dir "$ROOT/backend-service" > "$SANDBOX/backend.log" 2>&1 &
    echo "backend:$!" >> "$PIDFILE"
  )
  for _ in $(seq 1 20); do
    curl -sf "http://localhost:$BACKEND_PORT/" > /dev/null 2>&1 && break
    sleep 0.5
  done
  curl -sf "http://localhost:$BACKEND_PORT/" || { echo "backend failed to start, see $SANDBOX/backend.log"; exit 1; }
  echo
  echo "backend-service is up."
}

up_agent() {
  if ! curl -sf "http://localhost:$BACKEND_PORT/" > /dev/null 2>&1; then
    up_backend
  fi
  cat > "$SANDBOX/mcp_servers.json" <<EOF
{
  "budget-tracker": {
    "transport": "streamable_http",
    "url": "http://localhost:$BACKEND_PORT/mcp"
  }
}
EOF
  "$PY" - <<PYEOF
import psycopg
conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/postgres", autocommit=True)
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname='$PGDB'")
if not cur.fetchone():
    cur.execute("CREATE DATABASE $PGDB")
conn.close()
PYEOF
  GROQ_API_KEY="$(grep '^GROQ_API_KEY=' "$ROOT/agent-service/.env" | cut -d= -f2-)"
  GROQ_MODEL="$(grep '^GROQ_MODEL=' "$ROOT/agent-service/.env" | cut -d= -f2-)"
  echo "Starting agent-service on :$AGENT_PORT (isolated Postgres DB '$PGDB', MCP -> sandboxed backend)"
  (
    cd "$ROOT/agent-service"
    GROQ_API_KEY="$GROQ_API_KEY" GROQ_MODEL="$GROQ_MODEL" \
    DATABASE_URL="postgresql://postgres:postgres@localhost:5432/$PGDB" \
    HOST=0.0.0.0 PORT="$AGENT_PORT" RELOAD=false SUMMARIZATION_KEEP_MESSAGES=20 \
    MCP_CONFIG_PATH="$SANDBOX/mcp_servers.json" \
    nohup "$PY" src/main.py > "$SANDBOX/agent.log" 2>&1 &
    echo "agent:$!" >> "$PIDFILE"
  )
  for _ in $(seq 1 40); do
    grep -q "Application startup complete" "$SANDBOX/agent.log" 2>/dev/null && break
    sleep 0.5
  done
  grep -q "Application startup complete" "$SANDBOX/agent.log" || { echo "agent failed to start, see $SANDBOX/agent.log"; exit 1; }
  echo "agent-service is up."
}

cmd_up() {
  case "${1:-backend}" in
    backend) up_backend ;;
    agent) up_agent ;;
    *) echo "usage: driver.sh up backend|agent"; exit 1 ;;
  esac
}

cmd_smoke() {
  echo "== health ==" ; curl -sf "http://localhost:$BACKEND_PORT/"; echo
  echo "== summary 10/2023 ==" ; curl -sf "http://localhost:$BACKEND_PORT/summary/10/2023" | head -c 300; echo
  echo "== classify ==" ; curl -sf -X POST "http://localhost:$BACKEND_PORT/classify" -H "Content-Type: application/json" -d '{"description": "Uber ride to airport"}'; echo
  echo "== query ==" ; curl -sf -X POST "http://localhost:$BACKEND_PORT/query" -H "Content-Type: application/json" -d '{"sql": "SELECT COUNT(*) as cnt FROM budget_tracker"}'; echo
  echo "== add/patch/delete transaction round-trip =="
  ADD=$(curl -sf -X POST "http://localhost:$BACKEND_PORT/transactions" -H "Content-Type: application/json" \
    -d '{"Date":"08/08/26","Description":"Smoke test","Category":"Food","Expenditure":1,"Year":2026,"Month":8,"Day":8}')
  echo "$ADD"
  ID=$(curl -sf "http://localhost:$BACKEND_PORT/transactions/8/2026" | "$PY" -c "import json,sys; print(json.load(sys.stdin)[-1]['id'])")
  curl -sf -X PATCH "http://localhost:$BACKEND_PORT/transactions/$ID" -H "Content-Type: application/json" -d '{"Expenditure": 2}'; echo
  curl -sf -X DELETE "http://localhost:$BACKEND_PORT/transactions/$ID"; echo
}

cmd_chat() {
  local session="${2:-driver-session}"
  AGENT_PORT="$AGENT_PORT" DRIVER_SESSION="$session" DRIVER_MESSAGE="$1" "$PY" -c '
import json, os, urllib.request
port = os.environ["AGENT_PORT"]
body = json.dumps({"session_id": os.environ["DRIVER_SESSION"], "message": os.environ["DRIVER_MESSAGE"]}).encode()
url = "http://localhost:" + port + "/chat/invoke"
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(req).read().decode())
'
}

cmd_resume() {
  local session="$1" decision="$2"
  AGENT_PORT="$AGENT_PORT" DRIVER_SESSION="$session" DRIVER_DECISION="$decision" "$PY" -c '
import json, os, urllib.request
port = os.environ["AGENT_PORT"]
body = json.dumps({"session_id": os.environ["DRIVER_SESSION"], "decisions": [{"type": os.environ["DRIVER_DECISION"]}]}).encode()
url = "http://localhost:" + port + "/chat/resume"
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(req).read().decode())
'
}

cmd_down() {
  if [ -f "$PIDFILE" ]; then
    while IFS=: read -r name pid; do
      kill "$pid" 2>/dev/null || true
    done < "$PIDFILE"
    rm -f "$PIDFILE"
  fi
  "$PY" - <<PYEOF || true
import psycopg
conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/postgres", autocommit=True)
cur = conn.cursor()
cur.execute("DROP DATABASE IF EXISTS $PGDB")
conn.close()
PYEOF
  echo "stopped services and dropped $PGDB"
}

case "${1:-}" in
  up) shift; cmd_up "$@" ;;
  smoke) cmd_smoke ;;
  chat) shift; cmd_chat "$@" ;;
  resume) shift; cmd_resume "$@" ;;
  down) cmd_down ;;
  *) echo "usage: driver.sh {up backend|up agent|smoke|chat <msg> [session]|resume <session> approve|reject|down}"; exit 1 ;;
esac
