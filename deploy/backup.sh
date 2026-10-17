#!/usr/bin/env bash
# Dump the SkillPulse database and upload it to the private backup bucket.
# Runs daily from the skillpulse-backup.timer systemd timer.
set -euo pipefail

cd /opt/skillpulse
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="skillpulse-backups-${ACCOUNT_ID}"
KEY="postgres/skillpulse-$(date -u +%Y-%m-%dT%H%M%SZ).dump"

docker compose --env-file deploy/.env --file deploy/compose.prod.yaml exec -T database \
  pg_dump --username skillpulse --dbname skillpulse --format custom \
  | aws s3 cp - "s3://${BUCKET}/${KEY}"

echo "Backup uploaded to s3://${BUCKET}/${KEY}"
