#!/usr/bin/env bash
# Load the synthetic demo dataset into the running database, and optionally
# link a Cognito user (by "sub") to the demo learner so they can sign in.
# Usage (on the server, as root): deploy/load-demo-data.sh [cognito-sub]
set -euo pipefail

cd /opt/skillpulse
COMPOSE=(docker compose --env-file deploy/.env --file deploy/compose.prod.yaml)

for sql_file in \
  data/sample/skillpulse_seed.sql \
  scripts/seed_demo_module_checks.sql \
  scripts/seed_demo_final_project.sql \
  scripts/seed_demo_practice.sql
do
  echo "Loading ${sql_file}"
  "${COMPOSE[@]}" exec -T database \
    psql -v ON_ERROR_STOP=1 -U skillpulse -d skillpulse < "${sql_file}"
done

if [[ -n "${1:-}" ]]; then
  echo "Linking Cognito user to Demo Learner One"
  # psql only substitutes :'sub' in SQL read from stdin, not in -c commands.
  "${COMPOSE[@]}" exec -T database \
    psql -v ON_ERROR_STOP=1 -v sub="$1" -U skillpulse -d skillpulse <<'SQL'
UPDATE users
SET auth_subject = :'sub'
WHERE id = '20000000-0000-0000-0000-000000000003';
SQL
fi

echo "Demo data loaded."
