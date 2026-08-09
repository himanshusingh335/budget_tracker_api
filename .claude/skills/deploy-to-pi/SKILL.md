---
name: deploy-to-pi
description: Build+push budget-tracker-api's Docker images and deploy them to the production Raspberry Pi. Use when asked to deploy, ship, release, or push changes live to the Pi.
---

Paths below are relative to the repo root (`<unit>` = this repo,
`budget_tracker_api/`), not to this skill directory.

This deploys to the **production** server — it's not sandboxed like
`run-budget-tracker-api`. Confirm with the user before running it unless
they've already explicitly asked for a deploy in this conversation.

## Run

```bash
bash .claude/skills/deploy-to-pi/deploy.sh          # tags images "latest"
bash .claude/skills/deploy-to-pi/deploy.sh v1.2.3   # or a specific tag
```

This does, in order:
1. `./docker_push.sh <tag>` — builds and pushes all four images
   (`mariox1105/budget-tracker-{backend,frontend,agent,nginx}`) to Docker Hub.
2. SSH to the Pi, `cd ~/budget-tracker && docker compose pull && docker compose up -d`.
3. SSH again to `docker compose restart nginx` (see gotcha below — always
   needed, not conditional).
4. curl `/app` and `/chat/sessions` through the Pi's nginx and fail loudly
   if either isn't a 200.

Requires: SSH key access to the Pi already set up (`ssh mariox@100.127.54.94`
with no password prompt), and `docker login` already done locally for the
`mariox1105` Docker Hub account.

## Gotcha: nginx caches upstream container IPs

`docker compose up -d` only recreates containers whose image actually
changed — e.g. deploying a frontend-only change recreates
`frontend-service` but leaves `backend-service` and `nginx` untouched. The
recreated container gets a **new internal Docker IP**, but nginx resolved
its upstream hostnames to IPs once at its own startup and doesn't
re-resolve them. Result: nginx keeps proxying to the dead old IP and every
request through it 502s, even though `docker compose ps` shows everything
"Up".

Symptom in `docker compose logs nginx`:
```
connect() failed (111: Connection refused) while connecting to upstream, ... upstream: "http://172.21.0.5:8000/..."
```

Fix: restart nginx (`docker compose restart nginx`) after *any* deploy that
recreates another service's container — the script above always does this
unconditionally rather than trying to detect which services changed, since
the restart is cheap and skipping it is the actual failure mode this
gotcha describes.

## Manual steps (if the script isn't suitable)

```bash
./docker_push.sh                                              # or a tag
ssh mariox@100.127.54.94 "cd ~/budget-tracker && docker compose pull && docker compose up -d"
ssh mariox@100.127.54.94 "cd ~/budget-tracker && docker compose restart nginx"
curl -s -o /dev/null -w '%{http_code}\n' http://100.127.54.94:8502/app
curl -s http://100.127.54.94:8502/chat/sessions
```

## Troubleshooting

- 502 on any route right after deploy — see the nginx-caching gotcha above;
  restart nginx.
- `ssh` hangs or asks for a password — SSH key isn't set up for this
  session/host; the user needs to do this themselves (suggest `! ssh-copy-id
  mariox@100.127.54.94` for them to run).
- `docker push` fails with `unauthorized` — not logged in to Docker Hub
  locally; the user needs to run `docker login` themselves.
- Check what's actually running on the Pi:
  `ssh mariox@100.127.54.94 "cd ~/budget-tracker && docker compose ps"`
- Tail logs for a specific service:
  `ssh mariox@100.127.54.94 "cd ~/budget-tracker && docker compose logs --tail=40 <service>"`
  (service names: `backend-service`, `frontend-service`, `agent-service`, `nginx`, `postgres`)
