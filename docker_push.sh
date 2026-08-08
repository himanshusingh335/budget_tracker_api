#!/usr/bin/env bash
set -euo pipefail

DOCKERHUB_USER="mariox1105"
TAG="${1:-latest}"

DIRS=(backend-service frontend-service agent-service nginx)
IMAGE_NAMES=(budget-tracker-backend budget-tracker-frontend budget-tracker-agent budget-tracker-nginx)

for i in "${!DIRS[@]}"; do
  dir="${DIRS[$i]}"
  image="$DOCKERHUB_USER/${IMAGE_NAMES[$i]}:$TAG"
  echo "Building $image ..."
  docker build -t "$image" "./$dir"

  echo "Pushing $image ..."
  docker push "$image"

  echo "Done: $image"
done
