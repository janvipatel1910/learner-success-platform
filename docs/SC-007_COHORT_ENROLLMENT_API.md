# SC-007 Cohort Enrollment and Roster API

## Validation Summary

SC-007 adds authenticated, organisation-scoped cohort enrollment and roster APIs to SkillPulse.

The implementation provides:

- Self-service cohort-membership listing
- Cohort roster access for administrators and assigned tutors
- Administrator-controlled learner and tutor enrollment
- Administrator-controlled membership lifecycle updates
- Database-enforced organisation and role eligibility
- Cross-organisation data isolation
- Duplicate-enrollment protection
- Strict request validation
- Deterministic pagination
- Controlled API error responses
- Real PostgreSQL integration coverage

## 1. Objective

The objective of SC-007 is to expose the existing `cohort_memberships` data model through secure FastAPI endpoints.

The API must ensure that:

- Every request is authenticated
- Every operation is scoped to one authorised organisation
- Learners can view only their own cohort memberships
- Tutors can read only rosters for cohorts to which they are actively assigned
- Administrators can read rosters and manage memberships
- Target users are active members of the same organisation
- Organisation roles map correctly to cohort roles
- Duplicate memberships are rejected
- Records from another organisation are never exposed
- Database failures return controlled responses

## 2. Architecture

The enrollment implementation is divided into three layers:

| Layer | Responsibility |
|---|---|
| API schemas | Validate membership request and response data |
| API routes | Apply authentication, RBAC, tutor assignment checks and HTTP errors |
| Database repository | Execute organisation-scoped eligibility and membership queries |

Implemented files:

- `backend/skillpulse/schemas/enrollment.py`
- `backend/skillpulse/db/cohort_memberships.py`
- `backend/skillpulse/api/routes/enrollments.py`
- `tests/backend/test_enrollment_schemas.py`
- `tests/backend/test_cohort_enrollments.py`
- `tests/backend/test_cohort_enrollment_database.py`

The enrollment router is registered in `backend/skillpulse/main.py` under the configured `/api/v1` prefix.

No new database migration is required because SC-001 already created the `cohort_memberships` table and its controlled enum types.

## 3. Authorization Model

Amazon Cognito-compatible bearer-token verification authenticates the user. PostgreSQL organisation and cohort memberships remain the source of authorization.

Every request requires:

- A valid bearer access token
- An `X-Organization-ID` request header
- An active SkillPulse user
- An active organisation
- An active membership in the selected organisation

Role permissions are:

| Operation | Student | Tutor | Admin |
|---|---:|---:|---:|
| List own memberships | Allowed | Allowed | Allowed |
| List cohort roster | Denied | Assigned cohort only | Allowed |
| Read one roster member | Denied | Assigned cohort only | Allowed |
| Add cohort member | Denied | Denied | Allowed |
| Update cohort member | Denied | Denied | Allowed |
| Delete cohort member | Not exposed | Not exposed | Not exposed |

A tutor's organisation role alone is insufficient for roster access. The tutor must also hold an active `tutor` membership in the requested cohort.

Administrators do not require a cohort assignment because their active organisation-level `admin` role authorises roster management.

## 4. API Endpoints

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/api/v1/catalog/my-cohort-memberships` | Student, tutor, admin |
| `GET` | `/api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/members` | Assigned tutor, admin |
| `GET` | `/api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/members/{membership_id}` | Assigned tutor, admin |
| `POST` | `/api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/members` | Admin |
| `PUT` | `/api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/members/{membership_id}` | Admin |

All five operations across three unique paths are included in the generated OpenAPI contract.

## 5. Enrollment Eligibility

Cohort membership is created only when all parent and target records satisfy the database rules.

The selected cohort must:

- Exist
- Belong to the selected course
- Belong to the authorised organisation

The target user must:

- Exist
- Have an active user status
- Hold an active membership in the same organisation
- Hold the organisation role required by the requested cohort role

The controlled role mapping is:

| Organisation role | Permitted cohort role |
|---|---|
| `student` | `learner` |
| `tutor` | `tutor` |
| `admin` | No automatic cohort role |

Client-provided roles are not trusted. Eligibility is resolved from PostgreSQL during the write operation.

A user cannot be enrolled twice in the same cohort because the database enforces `UNIQUE (cohort_id, user_id)`.


## 6. Request and Lifecycle Validation

Pydantic schemas enforce controlled values before write operations reach PostgreSQL.

Create requests require:

- A valid `user_id` UUID
- A `cohort_role` of `learner` or `tutor`
- An optional membership `status`

New memberships default to `active`.

Update requests require both editable fields:

- `cohort_role`
- `status`

Unknown request fields are rejected.

Supported membership states are:

| Status | Meaning |
|---|---|
| `invited` | Membership has been offered but is not yet active |
| `active` | Membership currently grants cohort participation |
| `inactive` | Membership has been disabled without deleting history |

The API does not expose destructive delete operations.

Changing a membership role requires the target user to hold the matching active organisation role.

A membership can still be changed to `inactive` with its existing cohort role after the target user's organisation eligibility has been removed. This allows administrators to safely disable stale access.

Reactivation requires the target user and matching organisation membership to be active again.

## 7. Pagination

Roster and self-membership list endpoints use deterministic offset pagination.

Query parameters are:

| Parameter | Rule | Default |
|---|---|---:|
| `limit` | Integer from 1 to 100 | 20 |
| `offset` | Integer greater than or equal to 0 | 0 |

Responses contain:

- `items`
- `total`
- `limit`
- `offset`

Roster ordering places tutors before learners and then sorts members by name and ID.

Self-membership ordering uses cohort start date descending, followed by cohort name and ID.

## 8. Organisation Data Isolation

Organisation scoping is applied inside every repository query rather than relying only on route-level checks.

Roster queries join:

- `cohort_memberships`
- `cohorts`
- `courses`
- `users`

A record is returned only when the cohort belongs to the requested course and that course belongs to the authorised organisation.

Self-membership queries use the authenticated user's database `user_id`. The client cannot provide another user's ID to retrieve their memberships.

Cross-organisation requests return no membership data.

This design prevents:

- Guessing UUIDs from another organisation
- Reading another organisation's roster
- Enrolling users into a foreign cohort
- Updating a foreign membership
- Viewing another user's self-membership list

## 9. Controlled Error Responses

| Status | Condition |
|---:|---|
| `401 Unauthorized` | Bearer credentials are missing or invalid |
| `403 Forbidden` | Organisation role is insufficient or tutor assignment is missing |
| `404 Not Found` | Cohort or membership is unavailable within the authorised scope |
| `404 Not Found` | Target user is missing or ineligible for the requested cohort role |
| `409 Conflict` | User already has a membership in the cohort |
| `422 Unprocessable Entity` | UUID, enum, pagination or payload validation fails |
| `503 Service Unavailable` | Enrollment database operation fails |

Database exception details are logged by class name but are not exposed to API clients.

The same scoped `404` behaviour is used for missing and inaccessible resources to avoid revealing cross-organisation record existence.

## 10. Database Operations

The repository uses parameterised SQLAlchemy statements and PostgreSQL transactions.

Enrollment creation uses one `INSERT ... SELECT` statement to validate:

- Cohort ownership
- Course ownership
- User activity
- Organisation-membership activity
- Organisation-to-cohort role mapping

The eligibility checks and insert therefore occur as one atomic database operation.

Membership updates use a scoped `UPDATE` with an eligibility `EXISTS` check.

Create and update operations fetch the resulting record within the same transaction before returning it to the API.

The database remains the final enforcement layer for:

- Foreign-key relationships
- Controlled enum values
- Unique cohort membership
- Cohort and course ownership


## 11. Automated Tests

SC-007 adds 32 focused automated tests.

### Schema tests

Seven schema tests verify:

- Default active status
- Controlled cohort roles
- Controlled membership statuses
- UUID validation
- Unknown-field rejection
- Required update fields

### API and authorization tests

Twenty-three route tests verify:

- Self-membership access for students, tutors and administrators
- Cross-organisation self-access denial
- Student roster denial
- Unassigned tutor roster denial
- Assigned tutor roster access
- Administrator roster access
- Administrator create and update operations
- Non-administrator write denial
- Duplicate-enrollment conflict handling
- Ineligible target handling
- Missing cohort and membership handling
- Invalid-role validation
- Controlled database-failure responses
- OpenAPI enrollment operations

### PostgreSQL integration tests

Two real-database tests verify:

- Seeded tutor and learner roster resolution
- Active cohort-tutor assignment checks
- Authenticated-user self-membership listing
- Cross-organisation query isolation
- Eligible learner enrollment
- Organisation-to-cohort role enforcement
- Duplicate membership constraint enforcement
- Membership retrieval and pagination
- Role-change rejection for an ineligible user
- Safe deactivation after organisation eligibility removal
- Reactivation rejection while eligibility remains inactive
- Test-data cleanup

## 12. Validation Results

The completed local validation produced:

- Ruff: all checks passed
- Non-integration suite: 108 passed
- PostgreSQL integration suite: 9 passed
- SC-007 schema tests: 7 passed
- SC-007 API and authorization tests: 23 passed
- SC-007 PostgreSQL tests: 2 passed
- OpenAPI enrollment contract: five operations verified
- Docker backend and migration images: built
- PostgreSQL and API containers: healthy
- Migration container: exited successfully with code 0
- API container user: verified as non-root `skillpulse`
- Missing bearer token on SC-007 endpoint: returned `401`
- Live OpenAPI enrollment contract: three paths and five operations verified
The first database-test attempt correctly failed closed because PostgreSQL was not running. After starting the healthy database service, all integration tests passed without code changes.

## 13. Security Decisions

SC-007 applies the following controls:

- Cognito-compatible access tokens establish external identity
- Database memberships establish application authorization
- Organisation IDs are resolved through authenticated membership context
- Self-service queries use the authenticated database user ID
- Tutor roster access requires an active cohort assignment
- Administrator writes require an active organisation admin role
- Target-user eligibility is checked inside write SQL
- Client-provided cohort roles are never accepted without database validation
- Cross-organisation records are filtered inside every repository query
- Duplicate memberships are blocked by a database unique constraint
- Parameterised SQL prevents value injection
- Raw database errors are hidden from clients
- Lifecycle status updates preserve history instead of deleting records

## 14. Scope Boundary

SC-007 implements cohort enrollment and roster management using the existing SkillPulse database model.

Included:

- Personal cohort-membership listing
- Scoped roster listing and member retrieval
- Administrator-controlled enrollment
- Administrator-controlled role and status updates
- Assigned-tutor roster access
- Organisation eligibility enforcement
- Pagination and OpenAPI documentation

Not included:

- Destructive membership deletion
- Bulk enrollment
- Invitation email delivery
- Waitlists
- Attendance management
- Cohort scheduling
- User-account creation
- Cognito user-pool provisioning
- Frontend enrollment screens

These capabilities can be added in later stories without weakening the SC-007 authorization boundary.

## 15. Acceptance Criteria

- [x] Authenticated users can list their own cohort memberships
- [x] Learners cannot access cohort rosters
- [x] Assigned active tutors can read their cohort roster
- [x] Unassigned tutors cannot read a cohort roster
- [x] Administrators can read and manage cohort memberships
- [x] Target users must be active organisation members
- [x] Student and tutor roles map to controlled cohort roles
- [x] Duplicate enrollment returns a controlled conflict
- [x] Cross-organisation access is blocked
- [x] Membership lifecycle updates avoid destructive deletion
- [x] Invalid payloads are rejected
- [x] Database failures return controlled responses
- [x] OpenAPI exposes all five enrollment operations
- [x] Unit, API and PostgreSQL integration tests pass
- [x] Technical and security documentation is complete

## Final Result

SC-007 provides a secure organisation-scoped enrollment boundary for SkillPulse.

Learners can see their own cohort participation, assigned tutors can access only their authorised rosters, and administrators can manage eligible learner and tutor memberships. PostgreSQL remains the source of role eligibility, tenant ownership and membership state.
