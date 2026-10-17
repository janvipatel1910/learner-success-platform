#!/usr/bin/env bash
# Pull the requested Git ref, rebuild the API image and restart the stack.
# Run on the EC2 instance as root, e.g. through AWS Systems Manager.
set -euo pipefail

APP_DIR=/opt/skillpulse
GIT_REF="${1:-main}"

cd "$APP_DIR"
git fetch --depth 1 origin "$GIT_REF"
git checkout --force FETCH_HEAD

docker build --tag skillpulse-api:latest --file backend/Dockerfile .
docker compose --env-file deploy/.env --file deploy/compose.prod.yaml up --detach --remove-orphans
docker image prune --force

# Install or refresh the daily database backup timer.
install -m 0644 deploy/skillpulse-backup.service deploy/skillpulse-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now skillpulse-backup.timer

echo "Deployed $(git rev-parse --short HEAD)"
