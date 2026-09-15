# SC-008 Class Session Management API

## Status

Implemented and locally validated.

## Objective

SC-008 adds authenticated, organisation-scoped class-session management to SkillPulse.

The API allows eligible learners, assigned tutors and administrators to view scheduled cohort sessions. Assigned tutors and administrators can also create and update sessions without exposing destructive deletion.

## Delivered Scope

- Cohort class-session listing
- Individual class-session retrieval
- Class-session creation
- Full class-session update
- Organisation-scoped database queries
- Active cohort-role authorization
- Administrator organisation-wide access
- Topic and course relationship validation
- Timezone-aware schedule validation
- Duplicate schedule protection
- Deterministic offset pagination
- Controlled API error responses
- OpenAPI registration for all four operations
- Unit, API, authorization and PostgreSQL integration tests

## API Operations

| Operation | Endpoint | Access |
|---|---|---|
| List cohort sessions | `GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions` | Eligible learner, assigned tutor or administrator |
| Get one class session | `GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}` | Eligible learner, assigned tutor or administrator |
| Create a class session | `POST /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions` | Assigned tutor or administrator |
| Update a class session | `PUT /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}` | Assigned tutor or administrator |

No destructive `DELETE` operation is exposed.

## Authentication and Organisation Context

Every class-session request requires:

- A verified Cognito-compatible bearer access token
- An active SkillPulse database user
- An active membership in the selected organisation
- The authorised organisation UUID in the `X-Organization-ID` header

Cognito establishes external identity. PostgreSQL remains the source of application authorization.

Token groups and client-provided roles are not trusted.

## Authorization Model

| Organisation role | Cohort requirement | Read sessions | Create sessions | Update sessions |
|---|---|---:|---:|---:|
| `student` | Active `learner` cohort membership | Yes | No | No |
| `tutor` | Active `tutor` cohort membership | Yes | Yes | Yes |
| `admin` | No cohort assignment required | Yes | Yes | Yes |

### Learner Access

An active student organisation member can read sessions only when the same database user holds an active `learner` membership in the requested cohort.

Learners cannot create or update class sessions.

### Tutor Access

An active tutor organisation member can read, create and update sessions only when the same database user holds an active `tutor` membership in the requested cohort.

A tutor assignment in another cohort does not grant access.

### Administrator Access

An active administrator can read, create and update class sessions across the selected organisation without holding a cohort membership.

Organisation boundaries still apply to every administrator query.

## Class Session Lifecycle

Supported status values are:

- `scheduled`
- `completed`
- `cancelled`

New sessions default to `scheduled`.

Cancellation is represented by changing the session status to `cancelled`. Records are retained for history and reporting.

## Request Schema

A create or update request contains:

```json
{
  "topic_id": "41000000-0000-0000-0000-000000000001",
  "title": "VPC Foundations",
  "scheduled_start": "2026-09-15T10:00:00+00:00",
  "scheduled_end": "2026-09-15T11:30:00+00:00",
  "delivery_link": "https://training.skillpulse.example/live/vpc-foundations",
  "recording_url": null,
  "status": "scheduled"
}
```

## Response Schema

A successful response includes the database-generated identity and audit timestamps:

```json
{
  "id": "50000000-0000-0000-0000-000000000001",
  "cohort_id": "42000000-0000-0000-0000-000000000001",
  "topic_id": "41000000-0000-0000-0000-000000000001",
  "title": "VPC Foundations",
  "scheduled_start": "2026-09-15T10:00:00Z",
  "scheduled_end": "2026-09-15T11:30:00Z",
  "delivery_link": "https://training.skillpulse.example/live/vpc-foundations",
  "recording_url": null,
  "status": "scheduled",
  "created_at": "2026-09-13T09:00:00Z",
  "updated_at": "2026-09-13T09:00:00Z"
}
```

List responses include:

- `items`
- `total`
- `limit`
- `offset`

## Validation Rules

- Unknown request fields are rejected.
- `topic_id` must be a valid UUID.
- Titles are stripped of surrounding whitespace.
- Titles must contain between 1 and 200 characters.
- `scheduled_start` must include timezone information.
- `scheduled_end` must include timezone information.
- `scheduled_end` must be later than `scheduled_start`.
- Delivery and recording URLs must use `http` or `https`.
- URLs are limited to 2048 characters.
- Status must be `scheduled`, `completed` or `cancelled`.
- Update requests must provide every mutable field.
- The selected topic must belong to the same course as the cohort.
- The same cohort cannot contain two sessions with the same scheduled start time.

## Pagination and Ordering

The session-list endpoint supports deterministic offset pagination:

- `limit`: minimum `1`, maximum `100`
- `offset`: minimum `0`

Results are ordered by:

1. `scheduled_start`
2. `id`

The secondary UUID ordering provides stable results when multiple records share equivalent ordering values.
## Database Scoping

Class-session repository queries enforce the complete relationship path:

```text
organisation -> course -> cohort -> class session
                         |
                         -> cohort membership

course -> topic
```

A session is accessible only when:

- The course belongs to the selected organisation.
- The cohort belongs to the selected course.
- The session belongs to the selected cohort.
- The topic belongs to the selected course.
- The authenticated user satisfies the required database-backed role rule.

Organisation scoping is applied inside SQL queries rather than relying only on route-level checks.

## Atomic Relationship Validation

Session creation uses an `INSERT ... SELECT` operation that validates the organisation, course, cohort and topic relationship during insertion.

Session updates validate the same relationship inside the scoped update operation.

This prevents a request from attaching a topic from another course, even if the supplied UUID exists.

## Duplicate Schedule Protection

The existing database constraint on:

```text
(cohort_id, scheduled_start)
```

prevents duplicate session start times inside the same cohort.

Database integrity errors caused by this constraint are converted into a controlled `409 Conflict` response.

## Controlled Error Responses

| Status | Meaning |
|---:|---|
| `401 Unauthorized` | Bearer token is missing or invalid |
| `403 Forbidden` | User lacks the required organisation or cohort permission |
| `404 Not Found` | Scoped course, cohort or session is inaccessible or does not exist |
| `409 Conflict` | A session already exists at that cohort start time |
| `422 Unprocessable Entity` | Request data or pagination is invalid |
| `503 Service Unavailable` | Authentication or class-session database service is unavailable |

Sensitive SQL and internal exception details are not returned to clients.

Scoped `404` responses avoid confirming whether records exist outside the authorised organisation.

## Security Controls

- Cognito-compatible access-token verification remains mandatory.
- PostgreSQL remains the authorization source.
- Client-provided roles are not trusted.
- Active organisation membership is required.
- Active learner enrollment is required for student reads.
- Active tutor assignment is required for tutor reads and writes.
- Administrator access remains organisation-scoped.
- Cross-organisation access is denied.
- Topic ownership is checked during database writes.
- Parameterised SQL is used for database values.
- Database constraints protect lifecycle and relationship integrity.
- Duplicate session scheduling is rejected.
- Unknown payload fields are rejected.
- Timezone-naive timestamps are rejected.
- Internal database errors are hidden.
- No destructive delete endpoint is exposed.
## Implementation Files

| File | Responsibility |
|---|---|
| `backend/skillpulse/schemas/class_sessions.py` | Request, response, status and validation schemas |
| `backend/skillpulse/db/class_sessions.py` | Organisation-scoped session repository |
| `backend/skillpulse/db/cohort_memberships.py` | Reusable active cohort-role resolution |
| `backend/skillpulse/api/routes/class_sessions.py` | API routes and authorization decisions |
| `backend/skillpulse/main.py` | Application router registration |
| `tests/backend/test_class_session_schemas.py` | Schema validation tests |
| `tests/backend/test_class_sessions.py` | API and authorization tests |
| `tests/backend/test_class_session_database.py` | PostgreSQL integration tests |

## OpenAPI Contract

The live application registers two class-session paths and four operations:

```text
GET  /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions
POST /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions
GET  /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}
PUT  /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}
```

No class-session delete operation appears in OpenAPI.

## Validation Evidence

- Ruff across `backend`, `scripts` and `tests`: passed
- Complete automated suite with PostgreSQL and seed tests: 159 passed
- Class-session schema tests: 12 passed
- Class-session API and authorization tests: 26 passed
- Class-session PostgreSQL integration tests: 4 passed
- Docker Compose configuration: passed
- Backend and migration images: built
- PostgreSQL and API containers: healthy
- Migration container: exited successfully with code `0`
- API container user: verified as non-root `skillpulse`
- Missing bearer token: returned `401`
- Seeded session reads: passed
- Cross-organisation query isolation: passed
- Learner cohort-role resolution: passed
- Tutor cohort-role resolution: passed
- Administrator authorization: passed
- Topic-to-course relationship protection: passed
- Duplicate schedule protection: passed
- Live OpenAPI contract: two paths and four operations verified

## Database Migration Decision

No new migration is required for SC-008.

The initial PostgreSQL model already contains the `class_sessions` table, lifecycle enum, foreign keys, schedule-duration constraint and cohort start-time uniqueness constraint required by this API.

SC-008 uses that existing schema through the new repository and API layers.
## Scope Boundary

SC-008 does not include:

- Attendance recording
- Learner understanding checks
- Session feedback
- Session notes
- Tutor observations
- Recording upload or storage
- Notification delivery
- Calendar-provider integration
- Recurring session generation
- Destructive session deletion
- Frontend session-management screens
- Cognito infrastructure provisioning

Attendance and post-session understanding workflows belong to SC-009.

## Acceptance Checklist

- [x] Session schemas implemented
- [x] Session repository implemented
- [x] Session list endpoint implemented
- [x] Session detail endpoint implemented
- [x] Session create endpoint implemented
- [x] Session update endpoint implemented
- [x] Learner read authorization implemented
- [x] Assigned-tutor read and write authorization implemented
- [x] Administrator read and write authorization implemented
- [x] Cross-organisation protection implemented
- [x] Topic relationship validation implemented
- [x] Duplicate scheduling protection implemented
- [x] Automated tests passed locally
- [x] PostgreSQL integration tests passed
- [x] OpenAPI contract verified
- [x] Technical documentation completed
