# SC-010: Learner Blocker and Tutor Intervention API

## 1. Summary

SC-010 adds authenticated, organisation-scoped learner blocker and tutor intervention workflows to SkillPulse.

Learners can report and review their own blockers. Assigned tutors and administrators can review cohort blockers, manage their lifecycle and record support interventions. Every blocker mutation is accompanied by an auditable event.

PostgreSQL remains the source of application authorization and workflow state.

## 2. Implemented Components

### API routes

`backend/skillpulse/api/routes/blocker_interventions.py`

Provides eight authenticated operations for:

* Personal blocker listing
* Personal blocker retrieval
* Learner blocker creation
* Cohort blocker listing
* Cohort blocker retrieval
* Staff-controlled blocker updates
* Tutor intervention creation
* Intervention completion

### Database repository

`backend/skillpulse/db/blocker_interventions.py`

Provides parameterised, organisation-scoped database operations for blockers, events and tutor interventions.

### Validation schemas

`backend/skillpulse/schemas/blocker_interventions.py`

Defines validated request and response models for the complete workflow.

### Application registration

The SC-010 router is registered in:

`backend/skillpulse/main.py`

### Automated tests

* `tests/backend/test_blocker_interventions_schemas.py`
* `tests/backend/test_blocker_interventions.py`
* `tests/backend/test_blocker_interventions_database.py`

## 3. API Operations

### Learner operations

#### List my blockers

```http
GET /api/v1/catalog/my-blockers
```

Returns only blockers belonging to the authenticated learner within the selected organisation.

Supported query parameters:

* `status_filter`
* `severity_filter`
* `limit`
* `offset`

#### Get my blocker

```http
GET /api/v1/catalog/my-blockers/{blocker_id}
```

Returns one blocker owned by the authenticated learner, including its event history and interventions.

#### Create my blocker

```http
POST /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/my-blockers
```

Creates a blocker for the authenticated learner when the learner has:

* An active SkillPulse user account
* An active `student` organisation membership
* An active `learner` membership in the selected cohort

### Staff operations

#### List cohort blockers

```http
GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/blockers
```

Returns a paginated blocker list for an administrator or an actively assigned cohort tutor.

Supported query parameters:

* `status_filter`
* `severity_filter`
* `limit`
* `offset`

#### Get cohort blocker

```http
GET /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/blockers/{blocker_id}
```

Returns a scoped blocker with its event timeline and tutor interventions.

#### Update cohort blocker

```http
PUT /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/blockers/{blocker_id}
```

Allows authorised staff to update:

* Assigned tutor
* Severity
* Status
* Resolution summary
* Audit comment

#### Create intervention

```http
POST /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/blockers/{blocker_id}/interventions
```

Creates a tutor intervention linked to an active blocker.

Intervention creation requires the authenticated user to be an active tutor assigned to the selected cohort.

#### Complete intervention

```http
PUT /api/v1/catalog/courses/{course_id}/cohorts/{cohort_id}/blockers/{blocker_id}/interventions/{intervention_id}
```

Completes a pending intervention with:

* A non-pending outcome
* An optional follow-up metric value
* An automatically recorded completion timestamp

## 4. Authorization Model

Cognito-compatible access tokens establish external identity. PostgreSQL determines application authorization.

Client-provided roles, identifiers and ownership claims are not trusted.

### Students

Students can:

* List only their own blockers
* Retrieve only their own blocker details
* Create blockers only for themselves
* Create blockers only in cohorts where they are active learners

Students cannot:

* Read cohort-wide blocker lists
* Assign tutors
* Change blocker status or severity
* Create or complete tutor interventions
* Access blockers belonging to another learner

### Tutors

Tutors can:

* Read cohort blockers only when actively assigned to that cohort
* Update blockers in their assigned cohorts
* Create interventions when actively assigned to the cohort
* Complete their own pending interventions

Tutors cannot:

* Access blockers from an unassigned cohort
* Access blockers from another organisation
* Complete another tutor’s intervention unless authorised as an administrator

### Administrators

Administrators can:

* List and retrieve organisation-scoped cohort blockers
* Update blocker assignments, severity, status and resolution details
* Complete scoped pending interventions

Intervention creation still requires active tutor assignment to the selected cohort so the recorded intervention always belongs to an eligible tutor.

## 5. Request Validation

### Blocker creation

A blocker creation request supports:

* `topic_id`
* `title`
* `description`
* `category`
* `severity`

Validation includes:

* Non-empty title
* Maximum title length of 200 characters
* Non-empty description
* Maximum description length of 5,000 characters
* Non-empty category
* Maximum category length of 80 characters
* Controlled severity enum
* Rejection of unknown request fields

Supported severity values:

* `low`
* `medium`
* `high`
* `critical`

New blockers start with the `open` status.

### Blocker updates

A blocker update supports:

* `assigned_tutor_id`
* `severity`
* `status`
* `resolution_summary`
* `comment`

Validation includes:

* At least one update field is required
* Status and severity cannot be explicitly set to `null`
* Empty comments and resolution summaries are rejected
* Unknown fields are rejected
* Unsupported workflow transitions are rejected

Supported blocker statuses:

* `open`
* `assigned`
* `waiting_student`
* `resolved`
* `closed`

### Intervention creation

An intervention creation request supports:

* `intervention_type`
* `action_taken`
* `baseline_metric`
* `baseline_value`

The baseline metric and baseline value must either both be supplied or both be omitted.

### Intervention completion

An intervention completion request supports:

* `outcome`
* `follow_up_value`

Supported completion outcomes:

* `improved`
* `no_change`
* `declined`

The `pending` outcome cannot be used to complete an intervention.

## 6. Blocker Lifecycle Rules

The API enforces the following workflow rules:

* New blockers begin in the `open` state.
* `assigned` and `waiting_student` blockers require an assigned tutor.
* The assigned tutor must be an active SkillPulse user.
* The assigned tutor must hold an active `tutor` organisation role.
* The assigned tutor must be actively assigned to the selected cohort.
* `resolved` and `closed` blockers require a resolution summary.
* Resolving or closing a blocker records `resolved_at`.
* Reopening a blocker clears its resolution timestamp and summary.
* Unsupported status transitions return a controlled conflict response.
* A closed blocker permits comments but rejects further workflow mutations.
* No destructive blocker delete endpoint is exposed.

## 7. Intervention Rules

* An intervention must belong to a scoped blocker.
* New interventions can be created only for active blockers.
* Active blocker statuses are `open`, `assigned` and `waiting_student`.
* The intervention learner, cohort and topic are derived from the blocker.
* Client-provided learner ownership is not accepted.
* The authenticated eligible tutor becomes the intervention owner.
* New interventions begin with the `pending` outcome.
* Only pending, incomplete interventions can be completed.
* Completion records a non-pending outcome and `completed_at`.
* Repeated completion attempts are rejected.
* Intervention creation and completion append corresponding blocker events.
* No destructive intervention delete endpoint is exposed.

## 8. Audit Events

Blocker mutations append records to `blocker_events`.

Supported workflow event types include:

* `created`
* `assigned`
* `unassigned`
* `severity_changed`
* `commented`
* `resolution_updated`
* Status-specific changes
* `intervention_created`
* `intervention_completed`

Each event records:

* Blocker ID
* Actor ID
* Event type
* Previous status when applicable
* New status when applicable
* Comment
* Creation timestamp

Blocker updates and their audit events execute in the same database transaction.

Intervention creation or completion and its corresponding audit event also execute atomically.

## 9. Database Scoping

Repository queries enforce organisation scope by joining:

* `blockers`
* `cohorts`
* `courses`
* `users`
* `organization_memberships`
* `cohort_memberships`

The authenticated organisation, course and cohort identifiers must all match the stored relationship.

Personal blocker queries additionally constrain records using the authenticated database user ID.

This prevents:

* Cross-organisation blocker access
* Cross-course access
* Cross-cohort access
* Learner impersonation
* Assignment to an ineligible tutor
* Linking an intervention to an unrelated blocker

All database values use parameterised SQL.

## 10. Concurrency and Transaction Safety

Blocker mutations use a transaction and lock the scoped blocker before applying changes.

This ensures that:

* The current status is evaluated consistently.
* Concurrent updates do not create inconsistent event history.
* A blocker update and its audit event either both succeed or both roll back.
* Intervention writes and their audit events remain atomic.
* Only pending interventions can be completed once.

## 11. Response Models

### Blocker response

A blocker response includes:

* Learner identity
* Cohort and course details
* Optional topic details
* Title and description
* Category
* Severity
* Status
* Assigned tutor details
* Opened and resolved timestamps
* Resolution summary
* Creation and update timestamps

### Blocker detail response

A blocker detail response extends the blocker response with:

* Ordered blocker event history
* Linked tutor interventions

### Tutor intervention response

An intervention response includes:

* Learner, cohort, topic and blocker identifiers
* Intervention type
* Action taken
* Baseline metric and value
* Follow-up value
* Outcome
* Tutor identity
* Start and completion timestamps
* Creation and update timestamps

## 12. Controlled Error Responses

The API returns controlled responses without exposing internal database details.

### `401 Unauthorized`

Returned when a valid bearer token is missing or invalid.

### `403 Forbidden`

Returned when:

* The authenticated role is not permitted
* A tutor is not assigned to the selected cohort
* A learner is not active in the selected cohort
* A tutor attempts to complete another tutor’s intervention

### `404 Not Found`

Returned when a resource cannot be found inside the authenticated scope.

Scoped `404` responses prevent disclosure of records belonging to another organisation, course, cohort or learner.

### `409 Conflict`

Returned for invalid workflow state, including:

* Unsupported blocker status transitions
* Mutating a closed blocker
* Creating an intervention for an inactive blocker
* Completing an intervention that is no longer pending

### `422 Unprocessable Content`

Returned when request schema or business-rule validation fails.

### `503 Service Unavailable`

Returned when a database operation fails.

Internal exception details are logged by class name and are not exposed to clients.

## 13. Database Migration Decision

No new database migration is required for SC-010.

The initial PostgreSQL schema already contains:

* `blocker_severity`
* `blocker_status`
* `blockers`
* `blocker_events`
* `tutor_interventions`
* Blocker and intervention indexes
* Open-blocker aging view
* Intervention-outcome view

The synthetic seed data also includes blocker, blocker-event and tutor-intervention records.

SC-010 adds the application repository, schemas, authorization rules, API routes and automated tests over the existing data model.

## 14. Automated Validation

### SC-010 tests

* Schema tests: 24 passed
* API, authorization and lifecycle tests: 30 passed
* PostgreSQL repository tests: 4 passed
* Total focused SC-010 tests: 58 passed

### Complete project validation

* Non-integration tests: 239 passed
* PostgreSQL integration tests: 21 passed
* Complete automated suite: 260 passed
* Ruff checks: passed
* OpenAPI operations registered: 8

The initial integration attempt occurred while PostgreSQL was unavailable on port `55432`. Once the database container reported healthy, all 21 integration tests passed.

## 15. Security Controls

* Cognito-compatible bearer authentication
* Database-backed organisation authorization
* Active-user validation
* Active organisation-membership validation
* Active cohort-membership validation
* Self-service learner ownership derived from authentication
* Assigned-tutor cohort authorization
* Administrator-controlled blocker management
* Parameterised SQL
* Atomic mutation and audit-event transactions
* Row locking for blocker updates
* Cross-organisation access protection
* Scoped `404` responses
* Controlled workflow conflicts
* Unknown request fields rejected
* Sensitive internal errors hidden from clients
* No destructive blocker or intervention endpoints
* No real users, AWS credentials or production secrets introduced

## 16. Scope Boundary

SC-010 does not include:

* Email or push notifications
* Automated tutor assignment
* SLA timers or escalation policies
* File attachments
* Real-time learner-tutor messaging
* Bulk blocker updates
* Destructive blocker deletion
* Destructive intervention deletion
* Frontend blocker-management screens
* Intervention analytics dashboards
* AI-generated intervention recommendations
* Cognito infrastructure provisioning

These capabilities can be implemented in future tasks.

## 17. Final Result

SC-010 provides SkillPulse with a secure and auditable blocker-support workflow.

Learners can report and review their own blockers, authorised staff can manage blocker progress, and eligible tutors can record measurable interventions. Organisation scoping, role checks, lifecycle validation, transaction safety and PostgreSQL constraints protect the workflow from cross-tenant access and inconsistent state.
