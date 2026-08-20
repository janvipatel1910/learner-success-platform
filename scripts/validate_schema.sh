#!/usr/bin/env bash

set -Eeuo pipefail

CONTAINER_NAME="${SKILLPULSE_TEST_CONTAINER:-skillpulse-schema-validation}"
POSTGRES_IMAGE="${SKILLPULSE_POSTGRES_IMAGE:-postgres:16-alpine}"
DATABASE_NAME="${SKILLPULSE_TEST_DB:-skillpulse_test}"
DATABASE_USER="postgres"
DATABASE_PASSWORD="skillpulse_test"
EXPECTED_TABLES=29
EXPECTED_VIEWS=7

SCRIPT_DIRECTORY="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
  pwd
)"
PROJECT_ROOT="$(
  cd -- "${SCRIPT_DIRECTORY}/.."
  pwd
)"
SCHEMA_FILE="${PROJECT_ROOT}/backend/database/schema.sql"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}

trap cleanup EXIT

echo "Starting SkillPulse PostgreSQL schema validation..."

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker engine is not running."
  exit 1
fi

if [[ ! -f "${SCHEMA_FILE}" ]]; then
  echo "ERROR: Schema file not found: ${SCHEMA_FILE}"
  exit 1
fi

cleanup

docker run \
  --name "${CONTAINER_NAME}" \
  -e POSTGRES_PASSWORD="${DATABASE_PASSWORD}" \
  -e POSTGRES_DB="${DATABASE_NAME}" \
  -d "${POSTGRES_IMAGE}" \
  >/dev/null

database_ready="false"

for attempt in {1..30}; do
  if docker exec "${CONTAINER_NAME}" \
    pg_isready \
    -U "${DATABASE_USER}" \
    -d "${DATABASE_NAME}" \
    >/dev/null 2>&1; then
    database_ready="true"
    break
  fi

  sleep 1
done

if [[ "${database_ready}" != "true" ]]; then
  echo "ERROR: PostgreSQL did not become ready."
  docker logs "${CONTAINER_NAME}"
  exit 1
fi

echo "PostgreSQL is ready."
echo "Executing schema..."

docker exec -i "${CONTAINER_NAME}" \
  psql \
  -v ON_ERROR_STOP=1 \
  -U "${DATABASE_USER}" \
  -d "${DATABASE_NAME}" \
  < "${SCHEMA_FILE}" \
  >/dev/null

table_count="$(
  docker exec "${CONTAINER_NAME}" \
    psql \
    -U "${DATABASE_USER}" \
    -d "${DATABASE_NAME}" \
    -Atc "
      SELECT COUNT(*)
      FROM information_schema.tables
      WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE';
    " |
    tr -d '[:space:]'
)"

view_count="$(
  docker exec "${CONTAINER_NAME}" \
    psql \
    -U "${DATABASE_USER}" \
    -d "${DATABASE_NAME}" \
    -Atc "
      SELECT COUNT(*)
      FROM information_schema.tables
      WHERE table_schema = 'public'
        AND table_type = 'VIEW';
    " |
    tr -d '[:space:]'
)"

if [[ "${table_count}" != "${EXPECTED_TABLES}" ]]; then
  echo "ERROR: Expected ${EXPECTED_TABLES} tables, found ${table_count}."
  exit 1
fi

if [[ "${view_count}" != "${EXPECTED_VIEWS}" ]]; then
  echo "ERROR: Expected ${EXPECTED_VIEWS} views, found ${view_count}."
  exit 1
fi

echo "Schema transaction completed successfully."
echo "Validated tables: ${table_count}"
echo "Validated views: ${view_count}"
echo "SkillPulse schema validation PASSED."
