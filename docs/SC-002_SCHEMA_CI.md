# SC-002 Automated PostgreSQL Schema Validation

## Implementation Summary

- Project: SkillPulse Learner Success OS
- Feature: SC-002 Schema CI
- Owner: Janvi Patel
- Implementation date: 20 August 2026
- Branch: `feature/sc-002-schema-ci`
- Local validation result: Passed
- GitHub Actions result: To be confirmed by pull-request checks

SC-002 converts the manual SC-001 database test into a repeatable DevOps workflow. Developers can validate the schema locally with one command, while GitHub Actions automatically runs the same validation for relevant pull requests and changes to `main`.

## Components Added

| File | Purpose |
|---|---|
| `compose.yaml` | Local PostgreSQL 16 development service |
| `scripts/validate_schema.sh` | Repeatable isolated schema test |
| `.github/workflows/schema-validation.yml` | Automated CI validation |
| `docs/SC-002_SCHEMA_CI.md` | Implementation and evidence |

## Local PostgreSQL Service

The Compose configuration provides:

- PostgreSQL 16 Alpine
- Configurable local database values
- Health checks using `pg_isready`
- Persistent named storage
- Read-only schema initialization mount
- Local default port `55432`
- No production credentials

Start the local database:

```bash
docker compose up -d
```

Check its health:

```bash
docker compose ps
```

Stop it without deleting data:

```bash
docker compose down
```

Delete the local development volume only when a completely fresh database is required:

```bash
docker compose down --volumes
```

## Automated Validation Script

Run the complete schema test:

```bash
./scripts/validate_schema.sh
```

The script performs the following steps:

1. Confirms the Docker engine is available
2. Confirms the schema file exists
3. Removes only a previous container with the dedicated test name
4. Starts an isolated PostgreSQL 16 container
5. Waits for the database health check
6. Executes the schema with `ON_ERROR_STOP=1`
7. Asserts that 29 base tables exist
8. Asserts that 7 analytics views exist
9. Fails immediately when an assertion is incorrect
10. Removes the temporary container on success or failure

The script can be executed from any project directory because it calculates the repository path from its own location.

## Local Test Evidence

Command:

```bash
./scripts/validate_schema.sh
```

Result:

```text
Starting SkillPulse PostgreSQL schema validation...
PostgreSQL is ready.
Executing schema...
Schema transaction completed successfully.
Validated tables: 29
Validated views: 7
SkillPulse schema validation PASSED.
```

Automatic cleanup was confirmed with:

```bash
docker ps -a \
  --filter name=skillpulse-schema-validation \
  --format "{{.Names}}"
```

Result: no container remained after validation.

## GitHub Actions Behaviour

Workflow name:

```text
PostgreSQL Schema Validation
```

The workflow runs when:

- A pull request targeting `main` changes database or validation files
- A push to `main` changes database or validation files
- A maintainer starts it manually with `workflow_dispatch`

Relevant paths include:

- `backend/database/**`
- `scripts/validate_schema.sh`
- `compose.yaml`
- `.github/workflows/schema-validation.yml`

## CI Validation Steps

The GitHub Actions job:

1. Checks out the repository
2. Runs `bash -n` against the validation script
3. Validates the Docker Compose configuration
4. Executes the full PostgreSQL schema test
5. Writes a result summary to the GitHub Actions job summary

The job uses:

- A read-only repository permission
- A ten-minute timeout
- Concurrency cancellation for outdated runs
- An Ubuntu GitHub-hosted runner
- The same validation script used locally

## Failure Conditions

CI fails when:

- Docker cannot start
- PostgreSQL does not become ready
- The schema file is missing
- PostgreSQL rejects any statement
- The transaction does not complete
- The table count differs from 29
- The analytics-view count differs from 7
- The validation script contains invalid Bash syntax
- The Compose configuration is invalid

## Security and Data Safety

- No real learners or tutors are used
- No AWS credentials are required
- No production database credentials are stored
- The test password is isolated and local-only
- The validation container exposes no host port
- The schema is mounted read-only during local Compose initialization
- GitHub Actions receives only read access to repository contents
- Temporary validation containers are removed automatically

## Acceptance Evidence

| Check | Result |
|---|---|
| Compose configuration validates locally | Passed |
| Bash syntax validation | Passed |
| Validation script is executable | Passed |
| PostgreSQL becomes ready | Passed |
| Schema transaction completes | Passed |
| 29 tables are asserted | Passed |
| 7 views are asserted | Passed |
| Automatic container cleanup | Passed |
| Pull-request trigger configured | Passed |
| Main-branch trigger configured | Passed |
| Manual workflow trigger configured | Passed |
| GitHub-hosted execution | Pending PR check |

## Career Evidence

SC-002 demonstrates:

- Docker container management
- PostgreSQL automation
- Bash scripting
- CI/CD pipeline design
- Failure handling and cleanup
- Infrastructure health checks
- GitHub Actions
- Repeatable database quality assurance
- DevOps documentation

## Final Result

SkillPulse now has one repeatable validation command for both local development and CI. Future database changes cannot be merged safely without PostgreSQL accepting the schema and the expected analytics objects being present.
