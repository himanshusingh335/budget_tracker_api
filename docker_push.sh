#!/usr/bin/env bash
set -euo pipefail

DOCKERHUB_USER="mariox1105"
IMAGE_NAME="budget-tracker-api"
FRONTEND_IMAGE="budget-tracker-frontend"
TAG="${1:-latest}"
FULL_IMAGE="$DOCKERHUB_USER/$IMAGE_NAME:$TAG"
FULL_FRONTEND_IMAGE="$DOCKERHUB_USER/$FRONTEND_IMAGE:$TAG"

echo "Building $FULL_IMAGE ..."
docker build -t "$FULL_IMAGE" .

echo "Pushing $FULL_IMAGE ..."
docker push "$FULL_IMAGE"

echo "Building $FULL_FRONTEND_IMAGE ..."
docker build -t "$FULL_FRONTEND_IMAGE" ../budget_tracker_flutter

echo "Pushing $FULL_FRONTEND_IMAGE ..."
docker push "$FULL_FRONTEND_IMAGE"

echo "Done: $FULL_IMAGE, $FULL_FRONTEND_IMAGE"
