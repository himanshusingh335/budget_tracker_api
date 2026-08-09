#!/bin/bash
# Nightly backup: dumps budget.db out of the running backend-service container
# and uploads it to S3. This is the checked-in source of truth for the script
# that runs via cron on the Pi (~/budget-tracker/budget-api-db-backup.sh) —
# keep both in sync if you change this.

set -e
set -o pipefail

CONTAINER_NAME="budget-tracker-backend-service-1"
SOURCE_PATH="/app/data"
TMP_DIR="/tmp/budget-tracker-backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
S3_BUCKET="budget-tracker-backups-358625410597"
S3_KEY="backups/backup_${TIMESTAMP}/budget.db"

mkdir -p "$TMP_DIR"

echo "Backing up from container: $CONTAINER_NAME"
docker cp "$CONTAINER_NAME:$SOURCE_PATH" "$TMP_DIR"

echo "Uploading to s3://$S3_BUCKET/$S3_KEY"
/usr/local/bin/aws s3 cp "$TMP_DIR/data/budget.db" "s3://$S3_BUCKET/$S3_KEY"
echo "S3 upload complete"

rm -rf "$TMP_DIR"
echo "Done"
