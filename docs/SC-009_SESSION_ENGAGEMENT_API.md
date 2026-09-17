# SC-009 Session Engagement API

## Status

Implemented and locally validated.

## Objective

SC-009 adds authenticated, organisation-scoped attendance and learner understanding checks to SkillPulse.

It allows assigned tutors and administrators to record attendance, while learners submit their own Green, Yellow or Red understanding check after a completed class session.

## Delivered Scope

* Session attendance roster
* Personal attendance retrieval
* Tutor and administrator attendance recording
* Session understanding-check roster
* Personal understanding-check retrieval
* Learner self-service understanding submission
* Active learner eligibility validation
* Completed-session write enforcement
* Attendance-duration validation
* Database-generated confidence scores
* Organisation-scoped repository queries
* Cross-organisation access protection
* Deterministic offset pagination
* Controlled API error responses
* OpenAPI registration for six operations
* Schema, API, authorization and PostgreSQL integration tests

## API Operations

| Operation                           | Endpoint                                                                                                    | Access                          |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------- |
| List session attendance             | `GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/attendance`              | Assigned tutor or administrator |
| Get personal attendance             | `GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/my-attendance`           | Eligible learner                |
| Record learner attendance           | `PUT /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/attendance/{learner_id}` | Assigned tutor or administrator |
| List understanding checks           | `GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/understanding-checks`    | Assigned tutor or administrator |
| Get personal understanding check    | `GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/my-understanding-check`  | Eligible learner                |
| Submit personal understanding check | `PUT /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/my-understanding-check`  | Eligible learner                |

No learner ID is accepted by the personal endpoints. They always use the authenticated database user ID.

## Authentication and Organisation Context

Every request requires:

* A verified Cognito-compatible bearer access token
* An active SkillPulse database user
* An active membership in the selected organisation
* The authorised organisation UUID in the `X-Organization-ID` header
* Access to the selected course, cohort and session

Cognito establishes external identity. PostgreSQL remains the source of application authorization.

Token groups and client-provided roles are not trusted.

## Authorization Model

| Organisation role | Cohort requirement            | Staff rosters | Record attendance | Personal engagement |
| ----------------- | ----------------------------- | ------------: | ----------------: | ------------------: |
| `student`         | Active `learner` membership   |            No |                No |                 Yes |
| `tutor`           | Active `tutor` membership     |           Yes |               Yes |                  No |
| `admin`           | No cohort assignment required |           Yes |               Yes |                  No |

### Learner Access

An active student organisation member can access personal engagement only when the same database user has an active learner membership in the requested cohort.

Learners can:

* Retrieve only their own attendance
* Retrieve only their own understanding check
* Submit or update only their own understanding check
* Submit understanding only after the session is completed

Learners cannot:

* View the cohort engagement roster
* Record attendance
* Submit understanding on behalf of another learner
* Supply another learner’s ID through a personal endpoint

### Tutor Access

An active tutor organisation member can list engagement and record attendance only when the same database user has an active tutor assignment in the requested cohort.

A tutor assignment in another cohort does not grant access.

Tutors cannot create or edit a learner’s understanding response.

### Administrator Access

An active administrator can list session engagement and record attendance across the selected organisation without holding a cohort membership.

Organisation, course, cohort and session boundaries still apply to every administrator query.

## Attendance Workflow

Attendance is recorded with an idempotent upsert operation.

A request contains:

```json
{
  "attendance_status": "present",
  "minutes_attended": 115
}
```

Submitting attendance for the same session and learner again updates the existing record rather than creating a duplicate.

The response includes:

* Database-generated attendance ID
* Session ID
* Learner ID
* Attendance status
* Minutes attended
* Database user who recorded the attendance
* Creation and update timestamps

Attendance writes are permitted only when:

* The session exists inside the selected organisation, course and cohort
* The session status is `completed`
* The target user is an active learner in that cohort
* The authenticated tutor is assigned to the cohort, or the user is an administrator
* Attended minutes do not exceed the session duration

## Understanding-Check Workflow

Learners can submit one understanding check per completed session.

A request contains:

```json
{
  "rating": "yellow",
  "comment": "I need more practice with route-table selection."
}
```

Supported ratings are:

* `green`
* `yellow`
* `red`

Submitting another response for the same learner and session updates the existing record.

The learner cannot supply `learner_id` or `confidence_score`. The API obtains the learner identity from the authenticated user, and PostgreSQL generates the confidence score.

## Confidence-Score Mapping

| Understanding rating | Confidence score |
| -------------------- | ---------------: |
| `green`              |              100 |
| `yellow`             |               60 |
| `red`                |               20 |

This mapping is generated by the database so clients cannot manipulate readiness inputs by providing their own score.

## Complete Learner Rosters

Staff list operations begin with the cohort’s active learner roster.

This means the response includes:

* Learners with recorded attendance
* Learners without recorded attendance
* Learners who submitted an understanding check
* Learners who have not submitted an understanding check

Missing engagement data is represented with null record fields rather than removing the learner from the roster.

This allows tutors and administrators to identify missing attendance and understanding submissions.

## Validation Rules

* Unknown request fields are rejected.
* Attendance status must use an allowed value.
* `minutes_attended` must be a non-negative integer.
* Attended minutes cannot exceed the scheduled session duration.
* Understanding rating must be `green`, `yellow` or `red`.
* Understanding comments are optional.
* Comments are stripped of surrounding whitespace.
* Only active cohort learners are eligible.
* Attendance and understanding writes require a completed session.
* Personal endpoints always use the authenticated user ID.
* Pagination `limit` must be between `1` and `100`.
* Pagination `offset` must be `0` or greater.
* Cross-organisation records are inaccessible.

## Pagination and Ordering

Staff roster endpoints support deterministic offset pagination:

* `limit`: minimum `1`, maximum `100`
* `offset`: minimum `0`

Responses include:

* `items`
* `total`
* `limit`
* `offset`

Stable learner ordering prevents records from moving unpredictably between pages.

## Database Scoping

Engagement repository queries enforce the complete relationship path:

```text
organisation
    -> course
        -> cohort
            -> class session
            -> active learner membership
                -> attendance
                -> understanding check
```

A record is accessible only when:

* The course belongs to the selected organisation.
* The cohort belongs to the selected course.
* The session belongs to the selected cohort.
* The learner has an active membership in that cohort.
* The authenticated user satisfies the required database-backed role rule.

Organisation scoping is enforced inside SQL queries rather than relying only on route-level checks.

## Atomic Upserts

Attendance and understanding writes use atomic database upsert operations.

The existing uniqueness rules ensure there can be only:

* One attendance record per learner and session
* One understanding check per learner and session

Repeated submissions update the existing record while preserving its database identity.

The scoped write operation also verifies session status and learner eligibility.

## Completed-Session Protection

Attendance and understanding data cannot be written while a session remains `scheduled`.

A write attempted before completion returns a controlled `409 Conflict` response.

This prevents premature engagement records from affecting future learner analytics.

## Controlled Error Responses

|                      Status | Meaning                                                      |
| --------------------------: | ------------------------------------------------------------ |
|          `401 Unauthorized` | Bearer token is missing or invalid                           |
|             `403 Forbidden` | User lacks the required organisation or cohort permission    |
|             `404 Not Found` | Scoped course, cohort, session or learner is inaccessible    |
|              `409 Conflict` | The session has not been completed                           |
| `422 Unprocessable Content` | Payload, pagination or attendance duration is invalid        |
|   `503 Service Unavailable` | Authentication or engagement database service is unavailable |

Sensitive SQL and internal exception details are not returned to clients.

Scoped responses avoid confirming whether records exist outside the authorised organisation.

## Security Controls

* Cognito-compatible access-token verification remains mandatory.
* PostgreSQL remains the authorization source.
* Client-provided roles are not trusted.
* Active organisation membership is required.
* Active learner enrollment is required for personal access.
* Active tutor assignment is required for tutor roster and attendance access.
* Administrator access remains organisation-scoped.
* Personal endpoints use the authenticated database user ID.
* Learners cannot alter another learner’s engagement.
* Staff cannot alter learner understanding responses.
* Cross-organisation access is denied.
* Writes require a completed session.
* Attendance duration is checked against the scheduled session duration.
* Confidence scores are generated by PostgreSQL.
* Parameterised SQL is used for database values.
* Database uniqueness rules protect record integrity.
* Unknown payload fields are rejected.
* Internal database errors are hidden.
* No destructive delete endpoint is exposed.

## Implementation Files

| File                                                  | Responsibility                                                        |
| ----------------------------------------------------- | --------------------------------------------------------------------- |
| `backend/skillpulse/schemas/session_engagement.py`    | Attendance and understanding request, response and validation schemas |
| `backend/skillpulse/db/session_engagement.py`         | Organisation-scoped engagement repository and atomic upserts          |
| `backend/skillpulse/api/routes/session_engagement.py` | API routes, role authorization and session-state checks               |
| `backend/skillpulse/main.py`                          | Engagement router registration                                        |
| `tests/backend/test_session_engagement_schemas.py`    | Schema validation tests                                               |
| `tests/backend/test_session_engagement.py`            | API, authorization and OpenAPI tests                                  |
| `tests/backend/test_session_engagement_database.py`   | PostgreSQL integration tests                                          |

## OpenAPI Contract

The application registers five paths and six operations:

```text
GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/attendance

PUT /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/attendance/{learner_id}

GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/my-attendance

GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/understanding-checks

GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/my-understanding-check

PUT /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/sessions/{session_id}/my-understanding-check
```

No engagement delete operation appears in OpenAPI.


## Validation Evidence

* Ruff across all SC-009 files: passed
* Complete automated suite with PostgreSQL and seed tests: 202 passed
* Non-integration tests: 185 passed
* PostgreSQL integration tests: 17 passed
* SC-009 schema tests: 16 passed
* SC-009 API and authorization tests: 23 passed
* SC-009 PostgreSQL integration tests: 4 passed
* Docker Compose configuration: passed
* Backend and migration images: built
* PostgreSQL and API containers: healthy
* Migration container: exited successfully with code `0`
* API container user: verified as non-root `skillpulse`
* Missing bearer token: returned `401`
* Unrecorded roster rows: passed
* Atomic attendance upsert: passed
* Atomic understanding upsert: passed
* Database-generated confidence scores: passed
* Completed-session enforcement: passed
* Attendance-duration validation: passed
* Learner eligibility enforcement: passed
* Cross-organisation query isolation: passed
* Controlled database failure response: passed
* OpenAPI contract: five paths and six operations verified

## Database Migration Decision

No new migration is required for SC-009.

The initial PostgreSQL model already contains the attendance and understanding-check structures, controlled status values, generated confidence score, foreign keys and uniqueness rules required by this API.

SC-009 uses the existing schema through new repository and API layers.

## Scope Boundary

SC-009 does not include:

* Session feedback surveys
* Tutor observations
* Learner blocker or support-request workflows
* Automated interventions
* Readiness aggregation
* Attendance trend dashboards
* Weak-topic analytics
* Notifications
* Frontend engagement screens
* Recording upload or storage
* Quiz or mock-exam scoring
* Lab evidence
* Certificate eligibility
* AI tutor functionality
* Cognito infrastructure provisioning

These capabilities belong to later SkillPulse milestones.

## Acceptance Checklist

* [x] Attendance schemas implemented
* [x] Understanding-check schemas implemented
* [x] Engagement repository implemented


* [x] Staff attendance roster implemented

* [x] Personal attendance endpoint implemented

* [x] Attendance upsert implemented

* [x] Staff understanding roster implemented

* [x] Personal understanding retrieval implemented

* [x] Personal understanding upsert implemented

* [x] Learner self-only access implemented

* [x] Assigned-tutor authorization implemented

* [x] Administrator authorization implemented

* [x] Completed-session enforcement implemented

* [x] Attendance-duration validation implemented

* [x] Database-generated confidence scores verified

* [x] Cross-organisation protection implemented

* [x] Automated tests passed locally

* [x] PostgreSQL integration tests passed

* [x] OpenAPI contract verified

* [x] Docker validation passed

* [x] Technical documentation completed
