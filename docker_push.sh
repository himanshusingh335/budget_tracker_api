#!/usr/bin/env bash
set -euo pipefail

DOCKERHUB_USER="mariox1105"
TAG="${1:-latest}"

declare -A SERVICES=(
  [backend-service]="budget-tracker-backend"
  [frontend-service]="budget-tracker-frontend"
  [agent-service]="budget-tracker-agent"
  [nginx]="budget-tracker-nginx"
)

for dir in "${!SERVICES[@]}"; do
  image="$DOCKERHUB_USER/${SERVICES[$dir]}:$TAG"
  echo "Building $image ..."
  docker build -t "$image" "./$dir"

  echo "Pushing $image ..."
  docker push "$image"

  echo "Done: $image"
done
