# SkillPulse Data Model

## Document Status

- Feature: SC-001 Product Data Model
- Owner: Janvi Patel
- Database: PostgreSQL
- Status: Initial design
- Scope: AWS and DevOps learner-success MVP

## 1. Design Goals

The data model must support:

- Multiple training organisations
- Student, tutor and administrator access
- Courses, topics, cohorts and class sessions
- Attendance and Green/Yellow/Red understanding checks
- Quizzes and 65-question mock exams
- Hands-on lab submissions
- Learner blockers and tutor resolution tracking
- Explainable exam-readiness scoring
- Confidence-versus-competence analysis
- Certificate eligibility
- Verified-source AI assistance
- Privacy-safe analytics and audit history

## 2. Database Conventions

- Primary keys use UUID
- Date and time fields use `TIMESTAMPTZ`
- Table and column names use `snake_case`
- Records include `created_at` and `updated_at`
- Important status values use controlled enums
- Calculated scores are stored with their model version
- Learner records are never committed to the public repository
- Analytics exports use anonymous learner identifiers

## 3. Identity and Organisation

### `organizations`

Stores training providers using SkillPulse.

| Column | Type | Purpose |
|---|---|---|
| id | UUID | Primary key |
| name | VARCHAR(150) | Organisation name |
| slug | VARCHAR(100) | Unique URL-safe identifier |
| status | VARCHAR(20) | active, inactive or pilot |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `users`

Stores platform identities without exposing passwords to analytics.

| Column | Type | Purpose |
|---|---|---|
| id | UUID | Primary key |
| auth_subject | VARCHAR(255) | External authentication identity |
| email | VARCHAR(255) | Unique login email |
| full_name | VARCHAR(150) | Display name |
| status | VARCHAR(20) | invited, active, suspended or archived |
| last_login_at | TIMESTAMPTZ | Most recent login |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `organization_memberships`

Allows a user to have a role inside an organisation.

| Column | Type | Purpose |
|---|---|---|
| id | UUID | Primary key |
| organization_id | UUID | References organizations |
| user_id | UUID | References users |
| role | VARCHAR(20) | student, tutor or admin |
| joined_at | TIMESTAMPTZ | Membership start |
| status | VARCHAR(20) | invited, active or inactive |

Unique constraint: `(organization_id, user_id, role)`

## 4. Courses and Cohorts

### `courses`

| Column | Type | Purpose |
|---|---|---|
| id | UUID | Primary key |
| organization_id | UUID | Course owner |
| title | VARCHAR(200) | Course title |
| code | VARCHAR(50) | Internal course code |
| description | TEXT | Course description |
| certification_name | VARCHAR(150) | Related certification |
| status | VARCHAR(20) | draft, active or archived |

### `topics`

| Column | Type | Purpose |
|---|---|---|
| id | UUID | Primary key |
| course_id | UUID | References courses |
| title | VARCHAR(200) | Topic name |
| sequence_number | INTEGER | Learning order |
| exam_domain | VARCHAR(150) | Certification domain |
| expected_hours | NUMERIC(5,2) | Estimated study time |

### `cohorts`

| Column | Type | Purpose |
|---|---|---|
| id | UUID | Primary key |
| course_id | UUID | References courses |
| name | VARCHAR(150) | Cohort name |
| start_date | DATE | Cohort start |
| end_date | DATE | Cohort end |
| delivery_mode | VARCHAR(20) | online, classroom or hybrid |
| status | VARCHAR(20) | planned, active or completed |

### `cohort_memberships`

| Column | Type | Purpose |
|---|---|---|
| id | UUID | Primary key |
| cohort_id | UUID | References cohorts |
| user_id | UUID | Student or tutor |
| cohort_role | VARCHAR(20) | learner or tutor |
| enrolled_at | TIMESTAMPTZ | Enrollment time |
| status | VARCHAR(20) | active, withdrawn or completed |

Unique constraint: `(cohort_id, user_id)`

## 5. Learning Activity

### `class_sessions`

Stores each scheduled teaching session.

Key fields:

- `id`
- `cohort_id`
- `topic_id`
- `title`
- `scheduled_start`
- `scheduled_end`
- `delivery_link`
- `recording_url`
- `status`

### `attendance_records`

Key fields:

- `id`
- `session_id`
- `learner_id`
- `attendance_status`: present, late, absent or excused
- `minutes_attended`
- `recorded_by`
- `recorded_at`

Unique constraint: `(session_id, learner_id)`

### `understanding_checks`

Captures the learner’s confidence immediately after class.

Key fields:

- `id`
- `session_id`
- `learner_id`
- `rating`: green, yellow or red
- `confidence_score`
- `comment`
- `submitted_at`

Unique constraint: `(session_id, learner_id)`

### `learning_resources`

Stores recordings, PDFs, notes and assignment links.

Key fields:

- `id`
- `course_id`
- `topic_id`
- `title`
- `resource_type`
- `storage_url`
- `source_name`
- `is_verified`
- `uploaded_by`
- `created_at`

## 6. Assessments

### `assessments`

Key fields:

- `id`
- `course_id`
- `title`
- `assessment_type`: quiz or mock_exam
- `question_count`
- `time_limit_minutes`
- `pass_percentage`
- `maximum_attempts`
- `status`

### `questions`

Key fields:

- `id`
- `topic_id`
- `question_text`
- `question_type`: single_choice or multiple_choice
- `options_json`
- `correct_answer_json`
- `explanation`
- `difficulty`
- `verified_source_id`
- `status`

### `assessment_questions`

Connects questions to assessments.

Key fields:

- `assessment_id`
- `question_id`
- `sequence_number`
- `marks`

### `assessment_attempts`

Key fields:

- `id`
- `assessment_id`
- `learner_id`
- `started_at`
- `submitted_at`
- `score`
- `percentage`
- `passed`
- `attempt_number`
- `status`

### `question_responses`

Key fields:

- `id`
- `attempt_id`
- `question_id`
- `selected_answer_json`
- `is_correct`
- `marks_awarded`
- `response_seconds`

## 7. Hands-On Labs

### `lab_tasks`

Key fields:

- `id`
- `course_id`
- `topic_id`
- `title`
- `instructions`
- `evidence_requirements`
- `maximum_score`
- `due_days`
- `status`

### `lab_submissions`

Key fields:

- `id`
- `lab_task_id`
- `learner_id`
- `submission_url`
- `evidence_json`
- `submitted_at`
- `review_status`
- `score`
- `tutor_feedback`
- `reviewed_by`
- `reviewed_at`

## 8. Blockers and Tutor Support

### `blockers`

Key fields:

- `id`
- `learner_id`
- `cohort_id`
- `topic_id`
- `title`
- `description`
- `category`
- `severity`: low, medium, high or critical
- `status`: open, assigned, waiting_student, resolved or closed
- `assigned_tutor_id`
- `opened_at`
- `resolved_at`
- `resolution_summary`

### `blocker_events`

Maintains the complete blocker history.

Key fields:

- `id`
- `blocker_id`
- `actor_id`
- `event_type`
- `old_status`
- `new_status`
- `comment`
- `created_at`

### `tutor_interventions`

Measures whether tutor support improved an outcome.

Key fields:

- `id`
- `learner_id`
- `cohort_id`
- `topic_id`
- `blocker_id`
- `intervention_type`
- `action_taken`
- `baseline_metric`
- `baseline_value`
- `follow_up_value`
- `outcome`
- `tutor_id`
- `started_at`
- `completed_at`

## 9. Explainable Readiness

### `readiness_models`

Stores versioned and configurable readiness rules.

Key fields:

- `id`
- `organization_id`
- `name`
- `version`
- `component_weights_json`
- `readiness_threshold`
- `minimum_mock_score`
- `minimum_lab_completion`
- `active_from`
- `active_to`
- `is_active`

### `readiness_snapshots`

Stores why a learner received a readiness score.

Key fields:

- `id`
- `learner_id`
- `cohort_id`
- `readiness_model_id`
- `quiz_component`
- `mock_component`
- `lab_component`
- `attendance_component`
- `blocker_component`
- `overall_score`
- `readiness_level`: not_ready, developing, nearly_ready or ready
- `explanation_json`
- `calculated_at`

Readiness weights must be configurable and must never be silently changed.

## 10. Certificate Eligibility

### `certificate_eligibility`

Key fields:

- `id`
- `learner_id`
- `cohort_id`
- `attendance_met`
- `assignment_met`
- `lab_met`
- `mock_score_met`
- `blockers_cleared`
- `is_eligible`
- `missing_requirements_json`
- `evaluated_at`

## 11. Verified AI Sources

### `verified_sources`

Only approved course sources can support AI tutor answers.

Key fields:

- `id`
- `course_id`
- `title`
- `source_type`
- `source_url`
- `document_version`
- `approved_by`
- `approved_at`
- `status`
- `checksum`

AI responses must reference at least one active verified source. If evidence is unavailable, the AI tutor must clearly say that it cannot verify the answer.

## 12. Audit History

### `audit_events`

Key fields:

- `id`
- `organization_id`
- `actor_id`
- `action`
- `entity_type`
- `entity_id`
- `metadata_json`
- `occurred_at`

Audit events are append-only and cannot be edited by normal users.

## 13. Planned Analytics Views

SQL views will provide reusable data for Python, Excel and Power BI:

- `learner_latest_readiness`
- `cohort_weak_topics`
- `open_blocker_aging`
- `confidence_competence_gap`
- `intervention_outcomes`
- `attendance_risk_summary`
- `certificate_eligibility_summary`

## 14. Confidence-versus-Competence Logic

Confidence comes from Green/Yellow/Red understanding checks.

Competence comes from:

- Quiz performance
- Mock-exam performance
- Lab completion and tutor review
- Topic-level question accuracy

The analytics layer will identify:

- High confidence and low competence
- Low confidence and high competence
- Consistently low confidence and competence
- Improvement after tutor intervention

Thresholds will be configurable and documented instead of being hidden inside application code.

## 15. Security and Privacy Rules

- Apply role-based access control
- Students can access only their own learner records
- Tutors can access assigned cohorts
- Administrators can access organisation-level analytics
- Do not store AWS secret keys in lab evidence
- Remove personal information from analytics exports
- Record sensitive administrative actions
- Define data-retention and deletion procedures
- Use synthetic data during public development

## 16. MVP Implementation Order

1. Organisations and users
2. Courses, topics and cohorts
3. Sessions, attendance and understanding checks
4. Assessments and attempts
5. Lab tasks and submissions
6. Blocker workflow
7. Readiness model and snapshots
8. Analytics views
9. Certificate eligibility
10. Verified-source AI support

## 17. Acceptance Criteria

SC-001 is complete when:

- Every MVP feature maps to a database entity
- Primary and foreign-key relationships are defined
- Duplicate records are prevented with constraints
- Readiness decisions remain explainable
- Analytics requirements are supported
- Privacy and role-access rules are documented
- PostgreSQL schema creation can begin without unresolved core entities
