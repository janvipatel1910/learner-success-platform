# SC-006 Course, Topic and Cohort Management API

## Validation Summary

SC-006 adds authenticated, organisation-scoped management APIs for the SkillPulse learning catalog.

The implementation provides:

- Course management
- Course-topic management
- Delivery-cohort management
- Read access for active students, tutors and administrators
- Write access restricted to administrators
- Cross-organisation data isolation
- Strict request validation
- Deterministic pagination
- Controlled API error responses
- Real PostgreSQL integration coverage

## 1. Objective

The objective of SC-006 is to expose the existing course, topic and cohort data model through secure FastAPI endpoints.

The API must ensure that:

- Every request is authenticated
- Every catalog operation is scoped to one authorised organisation
- Students and tutors cannot modify catalog records
- Administrators can create and update catalog records
- Records from another organisation are never exposed
- Invalid input is rejected before reaching the database
- Database conflicts and outages return controlled responses

## 2. Architecture

The catalog implementation is divided into three layers:

| Layer | Responsibility |
|---|---|
| API schemas | Validate request and response data |
| API routes | Apply authentication, RBAC and HTTP error handling |
| Database repositories | Execute organisation-scoped PostgreSQL queries |

Implemented files:

- `backend/skillpulse/schemas/catalog.py`
- `backend/skillpulse/api/routes/catalog.py`
- `backend/skillpulse/db/courses.py`
- `backend/skillpulse/db/topics.py`
- `backend/skillpulse/db/cohorts.py`

The catalog router is registered in `backend/skillpulse/main.py` under the configured `/api/v1` prefix.

## 3. Authorization Model

Amazon Cognito-compatible bearer-token verification authenticates the user. PostgreSQL organisation memberships remain the source of authorization.

Every catalog request requires:

- A valid bearer access token
- An `X-Organization-ID` request header
- An active user record
- An active organisation
- An active membership in the selected organisation

Role permissions are:

| Operation | Student | Tutor | Admin |
|---|---:|---:|---:|
| List records | Allowed | Allowed | Allowed |
| Read one record | Allowed | Allowed | Allowed |
| Create record | Denied | Denied | Allowed |
| Update record | Denied | Denied | Allowed |
| Delete record | Not exposed | Not exposed | Not exposed |

Lifecycle status fields are used instead of destructive delete endpoints.

## 4. API Endpoints

### Courses

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/api/v1/catalog/courses` | Student, tutor, admin |
| `POST` | `/api/v1/catalog/courses` | Admin |
| `GET` | `/api/v1/catalog/courses/{course_id}` | Student, tutor, admin |
| `PUT` | `/api/v1/catalog/courses/{course_id}` | Admin |

### Topics

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/api/v1/catalog/courses/{course_id}/topics` | Student, tutor, admin |
| `POST` | `/api/v1/catalog/courses/{course_id}/topics` | Admin |
| `GET` | `/api/v1/catalog/courses/{course_id}/topics/{topic_id}` | Student, tutor, admin |
| `PUT` | `/api/v1/catalog/courses/{course_id}/topics/{topic_id}` | Admin |

### Cohorts

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/api/v1/catalog/courses/{course_id}/cohorts` | Student, tutor, admin |
| `POST` | `/api/v1/catalog/courses/{course_id}/cohorts` | Admin |
| `GET` | `/api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}` | Student, tutor, admin |
| `PUT` | `/api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}` | Admin |

All 12 operations are included in the generated OpenAPI contract.

## 5. Request Validation

Pydantic schemas enforce the database and API rules before write operations execute.

### Course validation

- Title length: 1 to 200 characters
- Code length: 1 to 50 characters
- Course codes reject spaces and unsupported symbols
- Description length: maximum 5,000 characters
- Certification name length: maximum 150 characters
- Status restricted to `draft`, `active` or `archived`
- Unknown request fields rejected

### Topic validation

- Title length: 1 to 200 characters
- Sequence number must be positive
- Exam domain length: maximum 150 characters
- Expected hours must be positive
- Expected hours use controlled decimal precision
- Unknown request fields rejected

### Cohort validation

- Name length: 1 to 150 characters
- Start date is required
- End date cannot be earlier than the start date
- Delivery mode restricted to `online`, `classroom` or `hybrid`
- Status restricted to `planned`, `active` or `completed`
- Unknown request fields rejected

## 6. Pagination

Course, topic and cohort list endpoints use offset pagination.

Accepted parameters:

| Parameter | Rule | Default |
|---|---|---:|
| `limit` | Between 1 and 100 | 20 |
| `offset` | Zero or greater | 0 |

Responses contain:

- `items`
- `total`
- `limit`
- `offset`

Database queries include deterministic ordering to produce stable results.

## 7. Organisation Data Isolation

Course queries filter directly by `courses.organization_id`.

Topic and cohort queries join their parent course and require:

- The expected parent course ID
- The authorised organisation ID
- A matching course-to-child relationship

Create operations use `INSERT ... SELECT` from an organisation-owned course. If the parent course is not owned by the authorised organisation, no row is inserted.

Update operations combine the child ID, course ID and organisation ID in the same SQL statement.

This prevents a caller from accessing or modifying another organisation's catalog by changing URL identifiers.

## 8. Controlled Error Responses

| Condition | HTTP status | Response behaviour |
|---|---:|---|
| Missing or invalid token | `401` | Authentication rejected |
| Missing organisation role | `403` | Access denied |
| Course, topic or cohort unavailable in scope | `404` | Generic not-found response |
| Duplicate code, name, title or sequence | `409` | Generic conflict response |
| Invalid payload or pagination | `422` | Validation response |
| Database unavailable | `503` | Internal database details hidden |

Cross-organisation resource lookups use generic not-found behaviour at the repository boundary and never expose the existence of another tenant's record.

## 9. Automated Tests

SC-006 adds:

- `tests/backend/test_catalog_schemas.py`
- `tests/backend/test_catalog_courses.py`
- `tests/backend/test_catalog_topics.py`
- `tests/backend/test_catalog_cohorts.py`
- `tests/backend/test_catalog_database.py`

Coverage includes:

- Course, topic and cohort payload validation
- Student, tutor and administrator read access
- Administrator-only create and update access
- Cross-organisation request denial
- Organisation ID forwarding to repositories
- Pagination validation
- Not-found behaviour
- Duplicate-record conflict handling
- Database-unavailable handling
- Real PostgreSQL list and detail queries
- Real PostgreSQL create and update statements
- Child-resource parent ownership checks
- Temporary integration-record cleanup

## 10. Validation Results

Local validation completed successfully:

- Ruff: passed
- Non-integration tests: 78 passed
- PostgreSQL integration tests: 7 passed
- SC-006 schema tests: 7 passed
- Course API tests: 11 passed
- Topic API tests: 14 passed
- Cohort API tests: 13 passed
- SC-006 PostgreSQL repository tests: 2 passed
- OpenAPI catalog operations: 12 verified
- Real create and update lifecycle: passed
- Cross-organisation database isolation: passed
- Temporary test data cleanup: passed

## 11. Database Migration Decision

SC-006 does not require a new Alembic revision.

The baseline `0001` migration already contains the required:

- `courses` table
- `topics` table
- `cohorts` table
- PostgreSQL enum types
- Foreign keys
- Unique constraints
- Check constraints
- Update timestamp triggers

SC-006 adds application behaviour on top of this existing versioned schema.

## 12. Security Decisions

- Organisation identity comes from the authorised `X-Organization-ID` context
- Database queries never trust a client-supplied role
- Cognito token groups are not used as application roles
- Only database-backed organisation memberships grant access
- Write operations require the `admin` organisation role
- Cross-organisation data is not returned
- Internal SQL errors are not exposed to API clients
- No destructive delete endpoints are included
- Test data is fictional
- Temporary integration data is removed after validation

## 13. Scope Boundary

SC-006 covers course, topic and cohort catalog management.

The following remain outside this story:

- Cohort learner and tutor enrolment APIs
- Class-session scheduling APIs
- Learning-material upload APIs
- Attendance recording
- Understanding checks
- Assessments and quizzes
- Hands-on lab submissions
- Learner blocker workflows
- Readiness calculation
- Frontend catalog screens
- Production AWS deployment

## 14. Acceptance Criteria

- [x] Course schemas implemented
- [x] Topic schemas implemented
- [x] Cohort schemas implemented
- [x] Organisation-scoped repositories implemented
- [x] Read endpoints implemented
- [x] Administrator write endpoints implemented
- [x] Pagination implemented
- [x] Request validation implemented
- [x] Conflict handling implemented
- [x] Service-unavailable handling implemented
- [x] Cross-organisation access protected
- [x] OpenAPI operations verified
- [x] Unit and API tests passed
- [x] PostgreSQL integration tests passed
- [x] Documentation completed

## Final Result

SC-006 provides a tested and secure application API for managing SkillPulse courses, course topics and delivery cohorts.

The catalog can now serve authenticated students, tutors and administrators while maintaining database-backed role controls and organisation isolation.
