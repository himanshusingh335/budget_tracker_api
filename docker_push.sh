#!/usr/bin/env bash
set -euo pipefail

DOCKERHUB_USER="mariox1105"
IMAGE_NAME="budget-tracker-api"
TAG="${1:-latest}"
FULL_IMAGE="$DOCKERHUB_USER/$IMAGE_NAME:$TAG"

echo "Building $FULL_IMAGE ..."
docker build -t "$FULL_IMAGE" .

echo "Pushing $FULL_IMAGE ..."
docker push "$FULL_IMAGE"

echo "Done: $FULL_IMAGE"
