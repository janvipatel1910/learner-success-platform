#!/usr/bin/env bash
# Restore a backup into a SEPARATE scratch database and check it, without
# touching the live data. Usage: deploy/restore.sh [s3-key]   (default: newest)
set -euo pipefail

cd /opt/skillpulse
COMPOSE=(docker compose --env-file deploy/.env --file deploy/compose.prod.yaml)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="skillpulse-backups-${ACCOUNT_ID}"

KEY="${1:-$(aws s3api list-objects-v2 --bucket "$BUCKET" --prefix postgres/ \
  --query 'sort_by(Contents, &LastModified)[-1].Key' --output text)}"
echo "Restoring s3://${BUCKET}/${KEY} into scratch database restore_check"

"${COMPOSE[@]}" exec -T database dropdb --username skillpulse --if-exists restore_check
"${COMPOSE[@]}" exec -T database createdb --username skillpulse restore_check
aws s3 cp "s3://${BUCKET}/${KEY}" - \
  | "${COMPOSE[@]}" exec -T database pg_restore --username skillpulse --dbname restore_check --no-owner

"${COMPOSE[@]}" exec -T database psql --username skillpulse --dbname restore_check \
  -c "SELECT (SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM courses) AS courses;"
"${COMPOSE[@]}" exec -T database dropdb --username skillpulse restore_check
echo "Restore check passed."
