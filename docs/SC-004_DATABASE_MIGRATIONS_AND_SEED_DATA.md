# SC-004: Database Migrations and Synthetic Learner Data

## Validation Summary

SC-004 establishes version-controlled PostgreSQL migrations and a deterministic synthetic dataset for SkillPulse.

Validation completed successfully:

- Alembic baseline revision: `0001`
- Application tables: 29
- PostgreSQL enum types: 21
- Analytics views: 7
- Migration upgrade, downgrade and re-upgrade: passed
- Synthetic seed loading and idempotency: passed
- Unit and API tests: 9 passed
- PostgreSQL integration tests: 3 passed
- Ruff code-quality validation: passed
- Production seed-data protection: verified

## 1. Objective

The objectives of SC-004 were to:

- Replace one-time schema initialization with version-controlled migrations.
- Support repeatable database upgrades and controlled rollbacks.
- Apply migrations before the API starts.
- Create realistic but entirely fictional demonstration data.
- Populate every analytics view with meaningful test scenarios.
- Validate migrations and seed behavior automatically.
- Prevent synthetic seed data from running in production.

## 2. Implemented Architecture

The local application startup sequence is:

1. PostgreSQL starts and passes its health check.
2. The migration service applies all pending Alembic revisions.
3. The FastAPI service starts only after migration success.
4. The API readiness endpoint verifies PostgreSQL connectivity.

This prevents the API from starting against an outdated schema.

## 3. Baseline Schema Inventory

The `0001` baseline migration manages the complete SkillPulse PostgreSQL design.

| Database object | Count |
|---|---:|
| SkillPulse application tables | 29 |
| PostgreSQL enum types | 21 |
| Analytics views | 7 |
| Explicit performance indexes | 16 |
| Trigger functions | 2 |
| Table triggers | 23 |
| Required extensions | 2 |

The required extensions are:

- `pgcrypto`
- `citext`

The schema includes identity, organisations, courses, cohorts, sessions, attendance, assessments, labs, blockers, tutor interventions, readiness scoring, certificate eligibility, verified-source AI conversations and append-only audit history.

## 4. Alembic Implementation

Alembic configuration was added through:

- `alembic.ini`
- `backend/migrations/env.py`
- `backend/migrations/script.py.mako`
- `backend/migrations/versions/0001_create_initial_skillpulse_schema.py`
- `backend/migrations/sql/0001_initial_schema.up.sql`
- `backend/migrations/sql/0001_initial_schema.down.sql`

The migration environment reads the existing environment-based SkillPulse settings. Database credentials are not stored in the Alembic configuration file.

The baseline uses versioned SQL files because the schema contains PostgreSQL-specific features including:

- Enum types
- Generated columns
- JSONB constraints
- Partial and unique indexes
- PL/pgSQL functions
- Dynamically generated triggers
- Analytics views
- Transactional DDL

The outer `BEGIN` and `COMMIT` statements were removed from the migration SQL because Alembic manages the migration transaction.

## 5. Migration Execution

Apply all pending migrations:

```bash
python -m alembic upgrade head
```

Inspect the current revision:

```bash
python -m alembic current
```

Downgrade to the empty baseline:

```bash
python -m alembic downgrade base
```

The initial revision is:

```text
Revision ID: 0001
Parent: <base>
```

For an existing development database, the schema inventory was verified before it was stamped at revision `0001`.

## 6. Reversible Migration Validation

The migration was tested against an isolated PostgreSQL database.

After upgrade:

```text
30 tables | 7 views | 21 enums | revision 0001
```

The table count includes 29 SkillPulse tables and Alembic's `alembic_version` table.

After downgrade:

```text
1 table | 0 views | 0 enums | no current revision
```

The remaining table is Alembic's empty bookkeeping table.

After re-upgrade:

```text
30 tables | 7 views | 21 enums | revision 0001
```

This confirms that the baseline can be applied, reversed and applied again without manual database repair.

The downgrade intentionally retains `pgcrypto` and `citext`, because those extensions may be shared or may have existed before SkillPulse was installed.

## 7. Docker Compose Integration

The Docker image now includes the Alembic configuration and migration files.

Docker Compose contains a one-time `migration` service:

```text
database healthy
       ↓
migration completed successfully
       ↓
backend API started
```

Start PostgreSQL and apply migrations:

```bash
docker compose up -d database
docker compose run --rm migration
```

Start the complete stack:

```bash
docker compose up -d --build
```

A successful stack validation confirmed:

- PostgreSQL container healthy
- Migration container exited with code `0`
- FastAPI container healthy
- `/ready` reported the database as connected

## 8. Synthetic Demonstration Dataset

The deterministic dataset is stored in:

```text
data/sample/skillpulse_seed.sql
```

It contains 24 ordered insert operations covering the main product workflow.

The dataset includes:

- One fictional training organisation
- One administrator
- One tutor
- Two fictional learners
- One AWS certification course
- Course topics and an active cohort
- Class sessions and attendance records
- Learner understanding checks
- Learning resources and a verified source
- Quiz and mock-assessment scenarios
- Questions, attempts and responses
- Hands-on lab tasks and submissions
- Open and resolved learner blockers
- Tutor interventions
- Readiness models and snapshots
- Certificate eligibility results

All identities are fictional and use reserved `.example` email addresses.

No real learner, employer or production information is included.

## 9. Seed Runner

Synthetic data is loaded with:

```bash
python scripts/seed_synthetic_data.py
```

The runner:

- Uses the central environment-based database settings.
- Executes the versioned SQL dataset transactionally.
- Rolls back automatically if an insert fails.
- Supports safe repeated execution.
- Blocks execution when `ENVIRONMENT=production`.

The seed SQL uses fixed identifiers and conflict-safe inserts so it can be run repeatedly without duplicating the core dataset.

## 10. Seed Validation Results

Initial seed validation produced these core counts:

```text
users: 4
topics: 2
class_sessions: 2
assessments: 2
lab_submissions: 2
blockers: 2
```

After running the seed a second time, the important counts remained unchanged:

```text
users: 4
topics: 2
assessments: 2
blockers: 2
```

This confirms deterministic and idempotent behavior.

The production guard was also tested and correctly raised:

```text
RuntimeError: Synthetic seed data is blocked in production.
```

## 11. Analytics-View Coverage

The synthetic dataset populates every SkillPulse analytics view.

| Analytics view | Validated rows |
|---|---:|
| `learner_latest_readiness` | 2 |
| `open_blocker_aging` | 1 |
| `attendance_risk_summary` | 2 |
| `confidence_competence_gap` | 4 |
| `cohort_weak_topics` | 2 |
| `intervention_outcomes` | 2 |
| `certificate_eligibility_summary` | 2 |

The dataset supports demonstrations of:

- Learner readiness
- Attendance risk
- Confidence versus competence
- Weak cohort topics
- Blocker aging
- Tutor-intervention outcomes
- Certificate eligibility

## 12. Automated Testing

SC-004 adds tests for:

- Current Alembic revision
- Migration-managed database availability
- Synthetic seed loading
- Repeated seed execution
- Expected core record counts
- Expected analytics-view counts
- Production seed-data blocking

The integration tests are protected by environment flags:

```text
RUN_DATABASE_TESTS=true
RUN_SEED_TESTS=true
```

This keeps ordinary unit tests independent from PostgreSQL while allowing CI to validate the real database workflow.

## 13. Continuous Integration

Backend CI now watches changes to:

- Backend application code
- Database schema
- Alembic migrations
- Synthetic sample data
- Database scripts
- Docker configuration
- Compose configuration
- Backend tests
- Python project configuration

The PostgreSQL integration job performs this cycle:

```bash
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
pytest -m integration
```

Ruff validation now includes the scripts directory:

```bash
ruff check backend scripts tests
```

## 14. Local Validation Results

Code quality:

```text
All checks passed!
```

Unit and API tests:

```text
9 passed, 3 deselected
```

PostgreSQL integration tests:

```text
3 passed, 9 deselected
```

The temporary migration and seed-test databases were removed after validation.

## 15. Technical Issues Resolved

### Psycopg percent-placeholder conflict

The baseline schema contains PostgreSQL `format()` expressions using `%I`.

Executing the complete file through SQLAlchemy's driver-level helper caused Psycopg to interpret `%I` as a client-side placeholder and reject it.

The migration runner was changed to execute the SQL through the underlying Psycopg cursor. This preserves PostgreSQL's server-side `%I` formatting behavior.

The failed migration was verified to roll back completely, leaving zero partially created application tables.

### Synthetic blocker row mismatch

One synthetic blocker row originally contained fewer values than the insert column list.

The missing topic identifier was added, after which the full dataset loaded successfully.

### Local editable installation path

The project directory had moved from `Documents` to `Projects`, leaving the editable Python installation pointed at the previous location.

The editable installation was refreshed and verified to reference the current repository.

## 16. Security and Responsible Data Controls

The implementation includes these controls:

- No real learner data is stored in the repository.
- Synthetic identities use reserved `.example` addresses.
- Database credentials come from environment settings.
- The seed runner is blocked in production.
- Database passwords are handled through `SecretStr`.
- Migration failures are transactionally rolled back.
- Temporary validation databases are removed after testing.
- Application containers continue to run as the non-root `skillpulse` user.
- Existing PostgreSQL extensions are not destructively removed during rollback.

## 17. Acceptance Criteria

- [x] Alembic installed and configured
- [x] Environment-based migration connection implemented
- [x] Initial schema captured as revision `0001`
- [x] Database credentials excluded from Alembic configuration
- [x] Upgrade validated on a fresh PostgreSQL database
- [x] Downgrade validated
- [x] Re-upgrade validated
- [x] Existing development database safely stamped
- [x] Docker migration service implemented
- [x] Backend startup depends on successful migrations
- [x] Deterministic synthetic dataset created
- [x] Seed execution is idempotent
- [x] Production seed execution blocked
- [x] All seven analytics views populated
- [x] Unit and integration tests added
- [x] Backend CI migration cycle added
- [x] Ruff validation passed
- [x] Documentation updated

## 18. Next Steps

The next story should establish the authenticated application boundary:

- External identity integration
- Authenticated SkillPulse users
- Organisation membership resolution
- Student, tutor and administrator authorization
- Protected API routes
- Authorization and audit tests

## Final Result

SC-004 converts the SkillPulse database from a one-time schema script into a repeatable, reversible and CI-validated migration system.

It also provides a safe synthetic dataset that demonstrates the learner-success workflow and produces meaningful results across all seven analytics views without using real learner data.
