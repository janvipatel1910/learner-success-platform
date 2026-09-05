-- SkillPulse Learner Success OS
-- SC-001: Initial PostgreSQL data model
-- Owner: Janvi Patel
-- Run once against a new PostgreSQL database.


CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- =========================================================
-- CONTROLLED TYPES
-- =========================================================

CREATE TYPE organization_status AS ENUM (
    'pilot',
    'active',
    'inactive'
);

CREATE TYPE user_status AS ENUM (
    'invited',
    'active',
    'suspended',
    'archived'
);

CREATE TYPE membership_role AS ENUM (
    'student',
    'tutor',
    'admin'
);

CREATE TYPE membership_status AS ENUM (
    'invited',
    'active',
    'inactive'
);

CREATE TYPE course_status AS ENUM (
    'draft',
    'active',
    'archived'
);

CREATE TYPE cohort_status AS ENUM (
    'planned',
    'active',
    'completed'
);

CREATE TYPE cohort_role AS ENUM (
    'learner',
    'tutor'
);

CREATE TYPE delivery_mode AS ENUM (
    'online',
    'classroom',
    'hybrid'
);

CREATE TYPE session_status AS ENUM (
    'scheduled',
    'completed',
    'cancelled'
);

CREATE TYPE attendance_status AS ENUM (
    'present',
    'late',
    'absent',
    'excused'
);

CREATE TYPE understanding_rating AS ENUM (
    'green',
    'yellow',
    'red'
);

CREATE TYPE learning_resource_type AS ENUM (
    'recording',
    'pdf',
    'note',
    'assignment',
    'link'
);

CREATE TYPE assessment_type AS ENUM (
    'quiz',
    'mock_exam'
);

CREATE TYPE question_type AS ENUM (
    'single_choice',
    'multiple_choice'
);

CREATE TYPE assessment_status AS ENUM (
    'draft',
    'published',
    'archived'
);

CREATE TYPE attempt_status AS ENUM (
    'in_progress',
    'submitted',
    'expired'
);

CREATE TYPE lab_review_status AS ENUM (
    'submitted',
    'under_review',
    'changes_requested',
    'approved',
    'rejected'
);

CREATE TYPE blocker_severity AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

CREATE TYPE blocker_status AS ENUM (
    'open',
    'assigned',
    'waiting_student',
    'resolved',
    'closed'
);

CREATE TYPE readiness_level AS ENUM (
    'not_ready',
    'developing',
    'nearly_ready',
    'ready'
);

CREATE TYPE verified_source_status AS ENUM (
    'draft',
    'active',
    'retired'
);

-- =========================================================
-- IDENTITY AND ORGANISATION
-- =========================================================

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    slug CITEXT NOT NULL UNIQUE,
    status organization_status NOT NULL DEFAULT 'pilot',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_subject VARCHAR(255) UNIQUE,
    email CITEXT NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    status user_status NOT NULL DEFAULT 'invited',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE organization_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL
        REFERENCES organizations(id),
    user_id UUID NOT NULL
        REFERENCES users(id),
    role membership_role NOT NULL,
    status membership_status NOT NULL DEFAULT 'invited',
    joined_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_organization_membership
        UNIQUE (organization_id, user_id, role)
);

-- =========================================================
-- COURSES, TOPICS AND COHORTS
-- =========================================================

CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL
        REFERENCES organizations(id),
    title VARCHAR(200) NOT NULL,
    code VARCHAR(50) NOT NULL,
    description TEXT,
    certification_name VARCHAR(150),
    status course_status NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_course_code
        UNIQUE (organization_id, code)
);

CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL
        REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    sequence_number INTEGER NOT NULL,
    exam_domain VARCHAR(150),
    expected_hours NUMERIC(5,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_topic_sequence_positive
        CHECK (sequence_number > 0),
    CONSTRAINT ck_topic_expected_hours_positive
        CHECK (expected_hours IS NULL OR expected_hours > 0),
    CONSTRAINT uq_topic_sequence
        UNIQUE (course_id, sequence_number),
    CONSTRAINT uq_topic_title
        UNIQUE (course_id, title)
);

CREATE TABLE cohorts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL
        REFERENCES courses(id),
    name VARCHAR(150) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    delivery_mode delivery_mode NOT NULL,
    status cohort_status NOT NULL DEFAULT 'planned',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_cohort_date_range
        CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT uq_cohort_name
        UNIQUE (course_id, name)
);

CREATE TABLE cohort_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_id UUID NOT NULL
        REFERENCES cohorts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL
        REFERENCES users(id),
    cohort_role cohort_role NOT NULL,
    status membership_status NOT NULL DEFAULT 'active',
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cohort_membership
        UNIQUE (cohort_id, user_id)
);

-- =========================================================
-- CLASS SESSIONS AND LEARNING ACTIVITY
-- =========================================================

CREATE TABLE class_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_id UUID NOT NULL
        REFERENCES cohorts(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL
        REFERENCES topics(id),
    title VARCHAR(200) NOT NULL,
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    delivery_link TEXT,
    recording_url TEXT,
    status session_status NOT NULL DEFAULT 'scheduled',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_session_time_range
        CHECK (scheduled_end > scheduled_start),
    CONSTRAINT uq_cohort_session_time
        UNIQUE (cohort_id, scheduled_start)
);

CREATE TABLE attendance_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL
        REFERENCES class_sessions(id) ON DELETE CASCADE,
    learner_id UUID NOT NULL
        REFERENCES users(id),
    attendance_status attendance_status NOT NULL,
    minutes_attended INTEGER,
    recorded_by UUID
        REFERENCES users(id),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_attendance_minutes
        CHECK (minutes_attended IS NULL OR minutes_attended >= 0),
    CONSTRAINT uq_session_attendance
        UNIQUE (session_id, learner_id)
);

CREATE TABLE understanding_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL
        REFERENCES class_sessions(id) ON DELETE CASCADE,
    learner_id UUID NOT NULL
        REFERENCES users(id),
    rating understanding_rating NOT NULL,
    confidence_score SMALLINT GENERATED ALWAYS AS (
        CASE rating
            WHEN 'green' THEN 100
            WHEN 'yellow' THEN 60
            WHEN 'red' THEN 20
        END
    ) STORED,
    comment TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_session_understanding_check
        UNIQUE (session_id, learner_id)
);

CREATE TABLE learning_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL
        REFERENCES courses(id) ON DELETE CASCADE,
    topic_id UUID
        REFERENCES topics(id) ON DELETE SET NULL,
    title VARCHAR(200) NOT NULL,
    resource_type learning_resource_type NOT NULL,
    storage_url TEXT NOT NULL,
    source_name VARCHAR(200),
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_by UUID NOT NULL
        REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- VERIFIED COURSE SOURCES
-- =========================================================

CREATE TABLE verified_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL
        REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    source_url TEXT NOT NULL,
    document_version VARCHAR(50),
    approved_by UUID
        REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    status verified_source_status NOT NULL DEFAULT 'draft',
    checksum VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_verified_source_checksum
        UNIQUE (course_id, checksum),
    CONSTRAINT ck_active_source_is_approved
        CHECK (
            status <> 'active'
            OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
        )
);

-- =========================================================
-- ASSESSMENTS AND QUESTIONS
-- =========================================================

CREATE TABLE assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL
        REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    assessment_type assessment_type NOT NULL,
    question_count INTEGER NOT NULL,
    time_limit_minutes INTEGER,
    pass_percentage NUMERIC(5,2) NOT NULL,
    maximum_attempts INTEGER NOT NULL DEFAULT 3,
    status assessment_status NOT NULL DEFAULT 'draft',
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_assessment_question_count
        CHECK (question_count > 0),
    CONSTRAINT ck_mock_exam_question_count
        CHECK (
            assessment_type <> 'mock_exam'
            OR question_count = 65
        ),
    CONSTRAINT ck_assessment_time_limit
        CHECK (
            time_limit_minutes IS NULL
            OR time_limit_minutes > 0
        ),
    CONSTRAINT ck_assessment_pass_percentage
        CHECK (pass_percentage BETWEEN 0 AND 100),
    CONSTRAINT ck_assessment_maximum_attempts
        CHECK (maximum_attempts > 0),
    CONSTRAINT ck_published_assessment_date
        CHECK (
            status <> 'published'
            OR published_at IS NOT NULL
        ),
    CONSTRAINT uq_course_assessment_title
        UNIQUE (course_id, title)
);

CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID NOT NULL
        REFERENCES topics(id),
    question_text TEXT NOT NULL,
    question_type question_type NOT NULL,
    options_json JSONB NOT NULL,
    correct_answer_json JSONB NOT NULL,
    explanation TEXT NOT NULL,
    difficulty SMALLINT NOT NULL DEFAULT 3,
    verified_source_id UUID NOT NULL
        REFERENCES verified_sources(id),
    status assessment_status NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_question_options_array
        CHECK (
            jsonb_typeof(options_json) = 'array'
            AND jsonb_array_length(options_json) >= 2
        ),
    CONSTRAINT ck_correct_answer_array
        CHECK (
            jsonb_typeof(correct_answer_json) = 'array'
            AND jsonb_array_length(correct_answer_json) >= 1
        ),
    CONSTRAINT ck_single_choice_one_answer
        CHECK (
            question_type <> 'single_choice'
            OR jsonb_array_length(correct_answer_json) = 1
        ),
    CONSTRAINT ck_question_difficulty
        CHECK (difficulty BETWEEN 1 AND 5)
);

CREATE TABLE assessment_questions (
    assessment_id UUID NOT NULL
        REFERENCES assessments(id) ON DELETE CASCADE,
    question_id UUID NOT NULL
        REFERENCES questions(id),
    sequence_number INTEGER NOT NULL,
    marks NUMERIC(6,2) NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (assessment_id, question_id),
    CONSTRAINT ck_assessment_question_sequence
        CHECK (sequence_number > 0),
    CONSTRAINT ck_assessment_question_marks
        CHECK (marks > 0),
    CONSTRAINT uq_assessment_question_sequence
        UNIQUE (assessment_id, sequence_number)
);

CREATE TABLE assessment_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id UUID NOT NULL
        REFERENCES assessments(id),
    learner_id UUID NOT NULL
        REFERENCES users(id),
    attempt_number INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    score NUMERIC(8,2),
    percentage NUMERIC(5,2),
    passed BOOLEAN,
    status attempt_status NOT NULL DEFAULT 'in_progress',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_attempt_number
        CHECK (attempt_number > 0),
    CONSTRAINT ck_attempt_time_range
        CHECK (
            submitted_at IS NULL
            OR submitted_at >= started_at
        ),
    CONSTRAINT ck_attempt_percentage
        CHECK (
            percentage IS NULL
            OR percentage BETWEEN 0 AND 100
        ),
    CONSTRAINT ck_submitted_attempt_results
        CHECK (
            status <> 'submitted'
            OR (
                submitted_at IS NOT NULL
                AND score IS NOT NULL
                AND percentage IS NOT NULL
                AND passed IS NOT NULL
            )
        ),
    CONSTRAINT uq_learner_assessment_attempt
        UNIQUE (assessment_id, learner_id, attempt_number)
);

CREATE TABLE question_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL
        REFERENCES assessment_attempts(id) ON DELETE CASCADE,
    question_id UUID NOT NULL
        REFERENCES questions(id),
    selected_answer_json JSONB,
    is_correct BOOLEAN,
    marks_awarded NUMERIC(6,2),
    response_seconds INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_response_answer_array
        CHECK (
            selected_answer_json IS NULL
            OR jsonb_typeof(selected_answer_json) = 'array'
        ),
    CONSTRAINT ck_response_marks
        CHECK (
            marks_awarded IS NULL
            OR marks_awarded >= 0
        ),
    CONSTRAINT ck_response_seconds
        CHECK (
            response_seconds IS NULL
            OR response_seconds >= 0
        ),
    CONSTRAINT uq_attempt_question_response
        UNIQUE (attempt_id, question_id)
);

-- =========================================================
-- HANDS-ON LABS
-- =========================================================

CREATE TABLE lab_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL
        REFERENCES courses(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL
        REFERENCES topics(id),
    title VARCHAR(200) NOT NULL,
    instructions TEXT NOT NULL,
    evidence_requirements JSONB NOT NULL DEFAULT '{}'::JSONB,
    maximum_score NUMERIC(6,2) NOT NULL DEFAULT 100,
    due_days INTEGER,
    status assessment_status NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_lab_evidence_requirements
        CHECK (
            jsonb_typeof(evidence_requirements)
            IN ('object', 'array')
        ),
    CONSTRAINT ck_lab_maximum_score
        CHECK (maximum_score > 0),
    CONSTRAINT ck_lab_due_days
        CHECK (due_days IS NULL OR due_days > 0),
    CONSTRAINT uq_course_lab_title
        UNIQUE (course_id, title)
);

CREATE TABLE lab_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_task_id UUID NOT NULL
        REFERENCES lab_tasks(id),
    learner_id UUID NOT NULL
        REFERENCES users(id),
    submission_number INTEGER NOT NULL DEFAULT 1,
    submission_url TEXT,
    evidence_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    review_status lab_review_status NOT NULL DEFAULT 'submitted',
    score NUMERIC(6,2),
    tutor_feedback TEXT,
    reviewed_by UUID
        REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_lab_submission_number
        CHECK (submission_number > 0),
    CONSTRAINT ck_lab_submission_evidence
        CHECK (
            jsonb_typeof(evidence_json)
            IN ('object', 'array')
        ),
    CONSTRAINT ck_lab_submission_score
        CHECK (score IS NULL OR score >= 0),
    CONSTRAINT ck_lab_review_details
        CHECK (
            review_status IN ('submitted', 'under_review')
            OR (
                reviewed_by IS NOT NULL
                AND reviewed_at IS NOT NULL
            )
        ),
    CONSTRAINT uq_lab_submission_number
        UNIQUE (lab_task_id, learner_id, submission_number)
);

-- =========================================================
-- LEARNER BLOCKERS AND SUPPORT
-- =========================================================

CREATE TABLE blockers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id UUID NOT NULL
        REFERENCES users(id),
    cohort_id UUID NOT NULL
        REFERENCES cohorts(id),
    topic_id UUID
        REFERENCES topics(id),
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(80) NOT NULL,
    severity blocker_severity NOT NULL DEFAULT 'medium',
    status blocker_status NOT NULL DEFAULT 'open',
    assigned_tutor_id UUID
        REFERENCES users(id),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolution_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_blocker_resolution_time
        CHECK (
            resolved_at IS NULL
            OR resolved_at >= opened_at
        ),
    CONSTRAINT ck_resolved_blocker_details
        CHECK (
            status NOT IN ('resolved', 'closed')
            OR (
                resolved_at IS NOT NULL
                AND resolution_summary IS NOT NULL
            )
        )
);

CREATE TABLE blocker_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blocker_id UUID NOT NULL
        REFERENCES blockers(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL
        REFERENCES users(id),
    event_type VARCHAR(80) NOT NULL,
    old_status blocker_status,
    new_status blocker_status,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_blocker_event_change
        CHECK (
            old_status IS NOT NULL
            OR new_status IS NOT NULL
            OR comment IS NOT NULL
        )
);

CREATE TABLE tutor_interventions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id UUID NOT NULL
        REFERENCES users(id),
    cohort_id UUID NOT NULL
        REFERENCES cohorts(id),
    topic_id UUID
        REFERENCES topics(id),
    blocker_id UUID
        REFERENCES blockers(id),
    intervention_type VARCHAR(80) NOT NULL,
    action_taken TEXT NOT NULL,
    baseline_metric VARCHAR(100),
    baseline_value NUMERIC(10,2),
    follow_up_value NUMERIC(10,2),
    outcome VARCHAR(20) NOT NULL DEFAULT 'pending',
    tutor_id UUID NOT NULL
        REFERENCES users(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_intervention_outcome
        CHECK (
            outcome IN (
                'pending',
                'improved',
                'no_change',
                'declined'
            )
        ),
    CONSTRAINT ck_intervention_time_range
        CHECK (
            completed_at IS NULL
            OR completed_at >= started_at
        ),
    CONSTRAINT ck_completed_intervention_outcome
        CHECK (
            completed_at IS NULL
            OR outcome <> 'pending'
        )
);

-- =========================================================
-- EXPLAINABLE EXAM READINESS
-- =========================================================

CREATE TABLE readiness_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL
        REFERENCES organizations(id),
    name VARCHAR(150) NOT NULL,
    version VARCHAR(30) NOT NULL,
    component_weights_json JSONB NOT NULL,
    readiness_threshold NUMERIC(5,2) NOT NULL,
    minimum_mock_score NUMERIC(5,2) NOT NULL,
    minimum_lab_completion NUMERIC(5,2) NOT NULL,
    active_from TIMESTAMPTZ NOT NULL,
    active_to TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_readiness_weights_object
        CHECK (
            jsonb_typeof(component_weights_json) = 'object'
        ),
    CONSTRAINT ck_readiness_threshold
        CHECK (readiness_threshold BETWEEN 0 AND 100),
    CONSTRAINT ck_minimum_mock_score
        CHECK (minimum_mock_score BETWEEN 0 AND 100),
    CONSTRAINT ck_minimum_lab_completion
        CHECK (minimum_lab_completion BETWEEN 0 AND 100),
    CONSTRAINT ck_readiness_model_dates
        CHECK (
            active_to IS NULL
            OR active_to >= active_from
        ),
    CONSTRAINT uq_readiness_model_version
        UNIQUE (organization_id, name, version)
);

CREATE TABLE readiness_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id UUID NOT NULL
        REFERENCES users(id),
    cohort_id UUID NOT NULL
        REFERENCES cohorts(id),
    readiness_model_id UUID NOT NULL
        REFERENCES readiness_models(id),
    quiz_component NUMERIC(5,2) NOT NULL,
    mock_component NUMERIC(5,2) NOT NULL,
    lab_component NUMERIC(5,2) NOT NULL,
    attendance_component NUMERIC(5,2) NOT NULL,
    blocker_component NUMERIC(5,2) NOT NULL,
    overall_score NUMERIC(5,2) NOT NULL,
    readiness_level readiness_level NOT NULL,
    explanation_json JSONB NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_quiz_component
        CHECK (quiz_component BETWEEN 0 AND 100),
    CONSTRAINT ck_mock_component
        CHECK (mock_component BETWEEN 0 AND 100),
    CONSTRAINT ck_lab_component
        CHECK (lab_component BETWEEN 0 AND 100),
    CONSTRAINT ck_attendance_component
        CHECK (attendance_component BETWEEN 0 AND 100),
    CONSTRAINT ck_blocker_component
        CHECK (blocker_component BETWEEN 0 AND 100),
    CONSTRAINT ck_overall_readiness_score
        CHECK (overall_score BETWEEN 0 AND 100),
    CONSTRAINT ck_readiness_explanation_object
        CHECK (
            jsonb_typeof(explanation_json) = 'object'
        )
);

-- =========================================================
-- CERTIFICATE ELIGIBILITY
-- =========================================================

CREATE TABLE certificate_eligibility (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id UUID NOT NULL
        REFERENCES users(id),
    cohort_id UUID NOT NULL
        REFERENCES cohorts(id),
    readiness_snapshot_id UUID
        REFERENCES readiness_snapshots(id),
    attendance_met BOOLEAN NOT NULL DEFAULT FALSE,
    assignment_met BOOLEAN NOT NULL DEFAULT FALSE,
    lab_met BOOLEAN NOT NULL DEFAULT FALSE,
    mock_score_met BOOLEAN NOT NULL DEFAULT FALSE,
    blockers_cleared BOOLEAN NOT NULL DEFAULT FALSE,
    is_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    missing_requirements_json JSONB NOT NULL DEFAULT '[]'::JSONB,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_missing_requirements_array
        CHECK (
            jsonb_typeof(missing_requirements_json) = 'array'
        ),
    CONSTRAINT ck_certificate_eligibility_result
        CHECK (
            is_eligible = (
                attendance_met
                AND assignment_met
                AND lab_met
                AND mock_score_met
                AND blockers_cleared
            )
        )
);

-- =========================================================
-- VERIFIED-SOURCE AI TUTOR
-- =========================================================

CREATE TABLE ai_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL
        REFERENCES courses(id),
    learner_id UUID NOT NULL
        REFERENCES users(id),
    title VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE ai_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL
        REFERENCES ai_conversations(id) ON DELETE CASCADE,
    sender VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    answer_verified BOOLEAN NOT NULL DEFAULT FALSE,
    refusal_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_ai_message_sender
        CHECK (sender IN ('learner', 'assistant')),
    CONSTRAINT ck_ai_assistant_verification
        CHECK (
            sender <> 'assistant'
            OR answer_verified = TRUE
            OR refusal_reason IS NOT NULL
        )
);

CREATE TABLE ai_message_sources (
    message_id UUID NOT NULL
        REFERENCES ai_messages(id) ON DELETE CASCADE,
    verified_source_id UUID NOT NULL
        REFERENCES verified_sources(id),
    citation_label VARCHAR(150),
    relevance_score NUMERIC(5,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (message_id, verified_source_id),
    CONSTRAINT ck_ai_source_relevance
        CHECK (
            relevance_score IS NULL
            OR relevance_score BETWEEN 0 AND 1
        )
);

-- =========================================================
-- APPEND-ONLY AUDIT HISTORY
-- =========================================================

CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL
        REFERENCES organizations(id),
    actor_id UUID
        REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_audit_metadata_object
        CHECK (jsonb_typeof(metadata_json) = 'object')
);

CREATE FUNCTION prevent_audit_event_change()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'audit_events are append-only and cannot be changed';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_events_immutable
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_event_change();

-- =========================================================
-- AUTOMATIC UPDATED_AT TIMESTAMPS
-- =========================================================

CREATE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'organizations',
        'users',
        'organization_memberships',
        'courses',
        'topics',
        'cohorts',
        'cohort_memberships',
        'class_sessions',
        'attendance_records',
        'understanding_checks',
        'learning_resources',
        'verified_sources',
        'assessments',
        'questions',
        'assessment_attempts',
        'question_responses',
        'lab_tasks',
        'lab_submissions',
        'blockers',
        'tutor_interventions',
        'readiness_models',
        'ai_conversations'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I
             BEFORE UPDATE ON %I
             FOR EACH ROW
             EXECUTE FUNCTION set_updated_at()',
            'trg_' || target_table || '_updated_at',
            target_table
        );
    END LOOP;
END;
$$;

-- =========================================================
-- PERFORMANCE AND REPORTING INDEXES
-- =========================================================

CREATE INDEX idx_organization_memberships_user
    ON organization_memberships (user_id, organization_id);

CREATE INDEX idx_cohort_memberships_user
    ON cohort_memberships (user_id, cohort_id);

CREATE INDEX idx_sessions_cohort_start
    ON class_sessions (cohort_id, scheduled_start);

CREATE INDEX idx_attendance_learner
    ON attendance_records (learner_id, attendance_status);

CREATE INDEX idx_understanding_learner_session
    ON understanding_checks (learner_id, session_id);

CREATE INDEX idx_questions_topic_status
    ON questions (topic_id, status);

CREATE INDEX idx_assessment_attempts_learner
    ON assessment_attempts (
        learner_id,
        assessment_id,
        submitted_at DESC
    );

CREATE INDEX idx_lab_submissions_learner
    ON lab_submissions (
        learner_id,
        lab_task_id,
        submitted_at DESC
    );

CREATE INDEX idx_open_blockers
    ON blockers (cohort_id, severity, opened_at)
    WHERE status NOT IN ('resolved', 'closed');

CREATE INDEX idx_blocker_assigned_tutor
    ON blockers (assigned_tutor_id, status)
    WHERE assigned_tutor_id IS NOT NULL;

CREATE INDEX idx_interventions_learner
    ON tutor_interventions (
        learner_id,
        cohort_id,
        started_at DESC
    );

CREATE INDEX idx_readiness_snapshots_latest
    ON readiness_snapshots (
        learner_id,
        cohort_id,
        calculated_at DESC
    );

CREATE UNIQUE INDEX uq_active_readiness_model_per_org
    ON readiness_models (organization_id)
    WHERE is_active = TRUE;

CREATE INDEX idx_certificate_eligibility_latest
    ON certificate_eligibility (
        learner_id,
        cohort_id,
        evaluated_at DESC
    );

CREATE INDEX idx_ai_conversations_learner
    ON ai_conversations (learner_id, created_at DESC);

CREATE INDEX idx_audit_events_organization_time
    ON audit_events (organization_id, occurred_at DESC);

-- =========================================================
-- ANALYTICS VIEWS
-- =========================================================

CREATE VIEW learner_latest_readiness AS
SELECT DISTINCT ON (learner_id, cohort_id)
    id AS readiness_snapshot_id,
    learner_id,
    cohort_id,
    readiness_model_id,
    quiz_component,
    mock_component,
    lab_component,
    attendance_component,
    blocker_component,
    overall_score,
    readiness_level,
    explanation_json,
    calculated_at
FROM readiness_snapshots
ORDER BY learner_id, cohort_id, calculated_at DESC;

CREATE VIEW open_blocker_aging AS
SELECT
    id AS blocker_id,
    learner_id,
    cohort_id,
    topic_id,
    assigned_tutor_id,
    severity,
    status,
    opened_at,
    ROUND(
        EXTRACT(EPOCH FROM (NOW() - opened_at)) / 3600,
        2
    ) AS open_hours
FROM blockers
WHERE status NOT IN ('resolved', 'closed');

CREATE VIEW attendance_risk_summary AS
SELECT
    cs.cohort_id,
    ar.learner_id,
    COUNT(*) AS sessions_recorded,
    COUNT(*) FILTER (
        WHERE ar.attendance_status IN ('present', 'late')
    ) AS sessions_attended,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE ar.attendance_status IN ('present', 'late')
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS attendance_percentage
FROM attendance_records ar
JOIN class_sessions cs
    ON cs.id = ar.session_id
GROUP BY cs.cohort_id, ar.learner_id;

CREATE VIEW confidence_competence_gap AS
WITH confidence AS (
    SELECT
        uc.learner_id,
        cs.cohort_id,
        cs.topic_id,
        ROUND(AVG(uc.confidence_score), 2)
            AS average_confidence
    FROM understanding_checks uc
    JOIN class_sessions cs
        ON cs.id = uc.session_id
    GROUP BY
        uc.learner_id,
        cs.cohort_id,
        cs.topic_id
),
competence AS (
    SELECT
        aa.learner_id,
        cm.cohort_id,
        q.topic_id,
        ROUND(
            AVG(
                CASE
                    WHEN qr.is_correct = TRUE THEN 100.0
                    ELSE 0.0
                END
            ),
            2
        ) AS average_competence
    FROM question_responses qr
    JOIN assessment_attempts aa
        ON aa.id = qr.attempt_id
    JOIN assessments a
        ON a.id = aa.assessment_id
    JOIN questions q
        ON q.id = qr.question_id
    JOIN cohorts c
        ON c.course_id = a.course_id
    JOIN cohort_memberships cm
        ON cm.cohort_id = c.id
       AND cm.user_id = aa.learner_id
       AND cm.cohort_role = 'learner'
    WHERE
        aa.status = 'submitted'
        AND qr.is_correct IS NOT NULL
    GROUP BY
        aa.learner_id,
        cm.cohort_id,
        q.topic_id
)
SELECT
    confidence.learner_id,
    confidence.cohort_id,
    confidence.topic_id,
    confidence.average_confidence,
    competence.average_competence,
    ROUND(
        confidence.average_confidence
        - competence.average_competence,
        2
    ) AS confidence_gap,
    CASE
        WHEN (
            confidence.average_confidence
            - competence.average_competence
        ) >= 20 THEN 'overconfident_risk'
        WHEN (
            confidence.average_confidence
            - competence.average_competence
        ) <= -20 THEN 'underconfident'
        ELSE 'aligned'
    END AS gap_category
FROM confidence
JOIN competence
    ON competence.learner_id = confidence.learner_id
   AND competence.cohort_id = confidence.cohort_id
   AND competence.topic_id = confidence.topic_id;

CREATE VIEW cohort_weak_topics AS
SELECT
    cm.cohort_id,
    q.topic_id,
    COUNT(DISTINCT aa.learner_id) AS learners_assessed,
    COUNT(*) AS responses_recorded,
    ROUND(
        AVG(
            CASE
                WHEN qr.is_correct = TRUE THEN 100.0
                ELSE 0.0
            END
        ),
        2
    ) AS average_topic_score
FROM question_responses qr
JOIN assessment_attempts aa
    ON aa.id = qr.attempt_id
JOIN assessments a
    ON a.id = aa.assessment_id
JOIN questions q
    ON q.id = qr.question_id
JOIN cohorts c
    ON c.course_id = a.course_id
JOIN cohort_memberships cm
    ON cm.cohort_id = c.id
   AND cm.user_id = aa.learner_id
   AND cm.cohort_role = 'learner'
WHERE
    aa.status = 'submitted'
    AND qr.is_correct IS NOT NULL
GROUP BY cm.cohort_id, q.topic_id;

CREATE VIEW intervention_outcomes AS
SELECT
    id AS intervention_id,
    learner_id,
    cohort_id,
    topic_id,
    blocker_id,
    tutor_id,
    intervention_type,
    baseline_metric,
    baseline_value,
    follow_up_value,
    CASE
        WHEN baseline_value IS NOT NULL
         AND follow_up_value IS NOT NULL
        THEN follow_up_value - baseline_value
        ELSE NULL
    END AS measured_change,
    outcome,
    started_at,
    completed_at
FROM tutor_interventions;

CREATE VIEW certificate_eligibility_summary AS
SELECT DISTINCT ON (learner_id, cohort_id)
    id AS eligibility_id,
    learner_id,
    cohort_id,
    readiness_snapshot_id,
    attendance_met,
    assignment_met,
    lab_met,
    mock_score_met,
    blockers_cleared,
    is_eligible,
    missing_requirements_json,
    evaluated_at
FROM certificate_eligibility
ORDER BY learner_id, cohort_id, evaluated_at DESC;
