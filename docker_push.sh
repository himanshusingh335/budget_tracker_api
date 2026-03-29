#!/usr/bin/env bash
set -euo pipefail

DOCKERHUB_USER="mariox1105"
API_IMAGE="budget-tracker-api"
DASHBOARD_IMAGE="budget-tracker-dashboard"
TAG="${1:-latest}"

echo "Building $DOCKERHUB_USER/$API_IMAGE:$TAG ..."
docker build -t "$DOCKERHUB_USER/$API_IMAGE:$TAG" .

echo "Pushing $DOCKERHUB_USER/$API_IMAGE:$TAG ..."
docker push "$DOCKERHUB_USER/$API_IMAGE:$TAG"

echo "Building $DOCKERHUB_USER/$DASHBOARD_IMAGE:$TAG ..."
docker build -t "$DOCKERHUB_USER/$DASHBOARD_IMAGE:$TAG" -f Dockerfile.dashboard .

echo "Pushing $DOCKERHUB_USER/$DASHBOARD_IMAGE:$TAG ..."
docker push "$DOCKERHUB_USER/$DASHBOARD_IMAGE:$TAG"

echo "Done: $DOCKERHUB_USER/$API_IMAGE:$TAG, $DOCKERHUB_USER/$DASHBOARD_IMAGE:$TAG"
