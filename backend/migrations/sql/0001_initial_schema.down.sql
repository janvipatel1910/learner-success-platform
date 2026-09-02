-- Reverse the SkillPulse baseline schema.
-- pgcrypto and citext are intentionally retained because they may pre-exist.

DROP VIEW IF EXISTS
    certificate_eligibility_summary,
    intervention_outcomes,
    cohort_weak_topics,
    confidence_competence_gap,
    attendance_risk_summary,
    open_blocker_aging,
    learner_latest_readiness;

DROP TABLE IF EXISTS
    audit_events,
    ai_message_sources,
    ai_messages,
    ai_conversations,
    certificate_eligibility,
    readiness_snapshots,
    readiness_models,
    tutor_interventions,
    blocker_events,
    blockers,
    lab_submissions,
    lab_tasks,
    question_responses,
    assessment_attempts,
    assessment_questions,
    questions,
    assessments,
    verified_sources,
    learning_resources,
    understanding_checks,
    attendance_records,
    class_sessions,
    cohort_memberships,
    cohorts,
    topics,
    courses,
    organization_memberships,
    users,
    organizations
CASCADE;

DROP FUNCTION IF EXISTS prevent_audit_event_change();
DROP FUNCTION IF EXISTS set_updated_at();

DROP TYPE IF EXISTS
    verified_source_status,
    readiness_level,
    blocker_status,
    blocker_severity,
    lab_review_status,
    attempt_status,
    assessment_status,
    question_type,
    assessment_type,
    learning_resource_type,
    understanding_rating,
    attendance_status,
    session_status,
    delivery_mode,
    cohort_role,
    cohort_status,
    course_status,
    membership_status,
    membership_role,
    user_status,
    organization_status;
