#!/usr/bin/env bash
# Build+push all four service images and deploy them to the production
# Raspberry Pi. Run from the repo root.
set -euo pipefail

TAG="${1:-latest}"
PI_HOST="mariox@100.127.54.94"
PI_DIR="~/budget-tracker"
PI_URL="http://100.127.54.94:8502"

cd "$(dirname "$0")/../../.."

echo "=== 1/4: build + push images (tag: $TAG) ==="
./docker_push.sh "$TAG"

echo
echo "=== 2/4: pull + restart stack on Pi ==="
ssh "$PI_HOST" "cd $PI_DIR && docker compose pull && docker compose up -d"

echo
echo "=== 3/4: restart nginx (upstream IPs get stale whenever another ==="
echo "===      container is recreated — see SKILL.md gotcha)          ==="
ssh "$PI_HOST" "cd $PI_DIR && docker compose restart nginx"

echo
echo "=== 4/4: verify ==="
sleep 2
for path in /app /chat/sessions; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$PI_URL$path")
  echo "$path -> $code"
  if [ "$code" != "200" ]; then
    echo "FAILED: $path returned $code, check 'ssh $PI_HOST \"cd $PI_DIR && docker compose logs --tail=40\"'"
    exit 1
  fi
done

echo
echo "Deploy OK."
