# SC-001 PostgreSQL Schema Validation

## Validation Summary

- Project: SkillPulse Learner Success OS
- Feature: SC-001 Product Data Model
- Owner: Janvi Patel
- Validation date: 20 August 2026
- Branch: `feature/sc-001-product-data-model`
- Result: Passed

The initial SkillPulse database schema was executed successfully against a real PostgreSQL 16 database. The transaction completed with `COMMIT`, confirming that PostgreSQL accepted the tables, relationships, constraints, indexes, triggers and analytics views.

## Test Environment

| Component | Version |
|---|---|
| Operating system | macOS |
| Docker | 29.4.1 |
| Database image | `postgres:16-alpine` |
| Test database | `skillpulse_test` |
| Host test port | `55432` |
| Schema file | `backend/database/schema.sql` |

No real learner or tutor data was used during validation.

## Validation Commands

### 1. Start an isolated PostgreSQL container

```bash
docker run \
  --name skillpulse-postgres-test \
  -e POSTGRES_PASSWORD=skillpulse_test \
  -e POSTGRES_DB=skillpulse_test \
  -p 55432:5432 \
  -d postgres:16-alpine

```

### 2. Confirm database readiness

```bash
docker exec skillpulse-postgres-test \
  pg_isready -U postgres -d skillpulse_test
```

Result:

```text
/var/run/postgresql:5432 - accepting connections
```

### 3. Execute the complete schema

```bash
docker exec -i skillpulse-postgres-test \
  psql -v ON_ERROR_STOP=1 \
  -U postgres \
  -d skillpulse_test \
  < backend/database/schema.sql
```

Result:

```text
COMMIT
```

The `ON_ERROR_STOP=1` option ensured that validation would stop immediately if PostgreSQL detected an error.

### 4. Count created database objects

```bash
docker exec skillpulse-postgres-test \
  psql -U postgres -d skillpulse_test \
  -c "SELECT table_type, COUNT(*)
      FROM information_schema.tables
      WHERE table_schema = 'public'
      GROUP BY table_type
      ORDER BY table_type;"
```

Result:

| Object type | Count |
|---|---:|
| Base tables | 29 |
| Views | 7 |

### 5. Remove the temporary test container

```bash
docker rm -f skillpulse-postgres-test
```

Result:

```text
skillpulse-postgres-test
```

Only the temporary container was removed. Project files and the PostgreSQL Docker image were retained.

## Validated Capabilities

The successful schema execution validated support for:

- Multi-organisation user access
- Student, tutor and administrator roles
- Courses, topics and cohorts
- Class sessions and attendance
- Green/Yellow/Red understanding checks
- Verified learning resources
- Quizzes and 65-question mock exams
- Assessment attempts and question responses
- Hands-on lab submissions and reviews
- Learner blockers and resolution history
- Tutor interventions and outcome measurement
- Versioned exam-readiness models
- Explainable readiness snapshots
- Certificate eligibility
- Verified-source AI tutor records
- Append-only audit history
- Automatic `updated_at` triggers
- Reporting indexes
- Seven reusable analytics views

## Analytics Views Created

1. `learner_latest_readiness`
2. `open_blocker_aging`
3. `attendance_risk_summary`
4. `confidence_competence_gap`
5. `cohort_weak_topics`
6. `intervention_outcomes`
7. `certificate_eligibility_summary`

These views will be reused by Python analysis, Excel reports and Power BI dashboards.

## Acceptance Evidence

| Check | Result |
|---|---|
| PostgreSQL accepted the full schema | Passed |
| Transaction reached `COMMIT` | Passed |
| Tables were created | 29 |
| Analytics views were created | 7 |
| Foreign-key dependency order was valid | Passed |
| Constraints compiled successfully | Passed |
| Indexes compiled successfully | Passed |
| Trigger functions compiled successfully | Passed |
| No real learner data was used | Passed |
| Temporary test environment was removed | Passed |

## Known Next Steps

The following items belong to later development tasks:

- Add repeatable migration tooling
- Add automated schema validation in GitHub Actions
- Add synthetic seed data
- Test constraints with positive and negative cases
- Implement application-level role permissions
- Add PostgreSQL row-level security where appropriate
- Connect the FastAPI backend
- Validate analytics results against sample learner journeys

## Final Result

SC-001 produced an executable and validated PostgreSQL foundation for SkillPulse. The schema supports the product charter while preserving explainability, analytics readiness and responsible learner-data handling.
