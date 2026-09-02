-- SkillPulse synthetic demonstration dataset.
-- All people, emails and activity records below are fictional.
-- Safe to rerun: fixed UUIDs and ON CONFLICT DO NOTHING prevent duplicates.

INSERT INTO organizations (id, name, slug, status)
VALUES (
    '10000000-0000-0000-0000-000000000001',
    'SkillPulse Demo Academy',
    'skillpulse-demo-academy',
    'pilot'
)
ON CONFLICT DO NOTHING;

INSERT INTO users (id, email, full_name, status, last_login_at)
VALUES
    (
        '20000000-0000-0000-0000-000000000001',
        'admin@skillpulse.example',
        'Demo Admin',
        'active',
        '2026-08-28T08:00:00Z'
    ),
    (
        '20000000-0000-0000-0000-000000000002',
        'tutor@skillpulse.example',
        'Demo Tutor',
        'active',
        '2026-08-28T08:15:00Z'
    ),
    (
        '20000000-0000-0000-0000-000000000003',
        'learner.one@skillpulse.example',
        'Demo Learner One',
        'active',
        '2026-08-27T17:30:00Z'
    ),
    (
        '20000000-0000-0000-0000-000000000004',
        'learner.two@skillpulse.example',
        'Demo Learner Two',
        'active',
        '2026-08-26T18:10:00Z'
    )
ON CONFLICT DO NOTHING;

INSERT INTO organization_memberships (
    id,
    organization_id,
    user_id,
    role,
    status,
    joined_at
)
VALUES
    (
        '30000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000001',
        'admin',
        'active',
        '2026-08-01T09:00:00Z'
    ),
    (
        '30000000-0000-0000-0000-000000000002',
        '10000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000002',
        'tutor',
        'active',
        '2026-08-01T09:00:00Z'
    ),
    (
        '30000000-0000-0000-0000-000000000003',
        '10000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000003',
        'student',
        'active',
        '2026-08-02T09:00:00Z'
    ),
    (
        '30000000-0000-0000-0000-000000000004',
        '10000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000004',
        'student',
        'active',
        '2026-08-02T09:00:00Z'
    )
ON CONFLICT DO NOTHING;

INSERT INTO courses (
    id,
    organization_id,
    title,
    code,
    description,
    certification_name,
    status
)
VALUES (
    '40000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'AWS Solutions Architect Associate Readiness',
    'AWS-SAA-DEMO',
    'Synthetic course used to validate SkillPulse learner-success analytics.',
    'AWS Certified Solutions Architect - Associate',
    'active'
)
ON CONFLICT DO NOTHING;

INSERT INTO topics (
    id,
    course_id,
    title,
    sequence_number,
    exam_domain,
    expected_hours
)
VALUES
    (
        '41000000-0000-0000-0000-000000000001',
        '40000000-0000-0000-0000-000000000001',
        'Networking and VPC',
        1,
        'Design Secure Architectures',
        6
    ),
    (
        '41000000-0000-0000-0000-000000000002',
        '40000000-0000-0000-0000-000000000001',
        'Storage and S3',
        2,
        'Design Resilient Architectures',
        5
    )
ON CONFLICT DO NOTHING;

INSERT INTO cohorts (
    id,
    course_id,
    name,
    start_date,
    end_date,
    delivery_mode,
    status
)
VALUES (
    '42000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001',
    'Synthetic Pilot Cohort 2026',
    '2026-08-01',
    '2026-10-31',
    'online',
    'active'
)
ON CONFLICT DO NOTHING;

INSERT INTO cohort_memberships (
    id,
    cohort_id,
    user_id,
    cohort_role,
    status,
    enrolled_at
)
VALUES
    (
        '43000000-0000-0000-0000-000000000001',
        '42000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000002',
        'tutor',
        'active',
        '2026-08-01T09:00:00Z'
    ),
    (
        '43000000-0000-0000-0000-000000000002',
        '42000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000003',
        'learner',
        'active',
        '2026-08-02T09:00:00Z'
    ),
    (
        '43000000-0000-0000-0000-000000000003',
        '42000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000004',
        'learner',
        'active',
        '2026-08-02T09:00:00Z'
    )
ON CONFLICT DO NOTHING;

INSERT INTO class_sessions (
    id,
    cohort_id,
    topic_id,
    title,
    scheduled_start,
    scheduled_end,
    status
)
VALUES
    (
        '50000000-0000-0000-0000-000000000001',
        '42000000-0000-0000-0000-000000000001',
        '41000000-0000-0000-0000-000000000001',
        'VPC Foundations',
        '2026-08-05T09:00:00Z',
        '2026-08-05T11:00:00Z',
        'completed'
    ),
    (
        '50000000-0000-0000-0000-000000000002',
        '42000000-0000-0000-0000-000000000001',
        '41000000-0000-0000-0000-000000000002',
        'S3 Resilience and Security',
        '2026-08-12T09:00:00Z',
        '2026-08-12T11:00:00Z',
        'completed'
    )
ON CONFLICT DO NOTHING;

INSERT INTO attendance_records (
    id,
    session_id,
    learner_id,
    attendance_status,
    minutes_attended,
    recorded_by,
    recorded_at
)
VALUES
    (
        '51000000-0000-0000-0000-000000000001',
        '50000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000003',
        'present',
        120,
        '20000000-0000-0000-0000-000000000002',
        '2026-08-05T11:05:00Z'
    ),
    (
        '51000000-0000-0000-0000-000000000002',
        '50000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000003',
        'present',
        115,
        '20000000-0000-0000-0000-000000000002',
        '2026-08-12T11:05:00Z'
    ),
    (
        '51000000-0000-0000-0000-000000000003',
        '50000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000004',
        'late',
        75,
        '20000000-0000-0000-0000-000000000002',
        '2026-08-05T11:05:00Z'
    ),
    (
        '51000000-0000-0000-0000-000000000004',
        '50000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000004',
        'absent',
        0,
        '20000000-0000-0000-0000-000000000002',
        '2026-08-12T11:05:00Z'
    )
ON CONFLICT DO NOTHING;

INSERT INTO understanding_checks (
    id,
    session_id,
    learner_id,
    rating,
    comment,
    submitted_at
)
VALUES
    (
        '52000000-0000-0000-0000-000000000001',
        '50000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000003',
        'green',
        'Comfortable with subnet and routing concepts.',
        '2026-08-05T11:10:00Z'
    ),
    (
        '52000000-0000-0000-0000-000000000002',
        '50000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000003',
        'yellow',
        'Needs more practice with S3 security controls.',
        '2026-08-12T11:10:00Z'
    ),
    (
        '52000000-0000-0000-0000-000000000003',
        '50000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000004',
        'green',
        'Feels confident but needs assessment validation.',
        '2026-08-05T11:10:00Z'
    ),
    (
        '52000000-0000-0000-0000-000000000004',
        '50000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000004',
        'red',
        'Does not yet understand storage class selection.',
        '2026-08-12T11:10:00Z'
    )
ON CONFLICT DO NOTHING;

INSERT INTO verified_sources (
    id,
    course_id,
    title,
    source_type,
    source_url,
    document_version,
    approved_by,
    approved_at,
    status,
    checksum
)
VALUES (
    '60000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001',
    'AWS Architecture Documentation',
    'official_documentation',
    'https://docs.aws.amazon.com/',
    'synthetic-reference-v1',
    '20000000-0000-0000-0000-000000000001',
    '2026-08-01T10:00:00Z',
    'active',
    'skillpulse-synthetic-aws-reference-v1'
)
ON CONFLICT DO NOTHING;

INSERT INTO assessments (
    id,
    course_id,
    title,
    assessment_type,
    question_count,
    time_limit_minutes,
    pass_percentage,
    maximum_attempts,
    status,
    published_at
)
VALUES (
    '61000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001',
    'Synthetic Topic Check',
    'quiz',
    2,
    10,
    70,
    3,
    'published',
    '2026-08-13T09:00:00Z'
)
ON CONFLICT DO NOTHING;

INSERT INTO questions (
    id,
    topic_id,
    question_text,
    question_type,
    options_json,
    correct_answer_json,
    explanation,
    difficulty,
    verified_source_id,
    status
)
VALUES
    (
        '62000000-0000-0000-0000-000000000001',
        '41000000-0000-0000-0000-000000000001',
        'Which component provides outbound internet access for private IPv4 subnets?',
        'single_choice',
        '["Internet gateway", "NAT gateway", "VPC peering", "Route table"]',
        '["NAT gateway"]',
        'A NAT gateway permits outbound IPv4 connectivity without accepting unsolicited inbound connections.',
        3,
        '60000000-0000-0000-0000-000000000001',
        'published'
    ),
    (
        '62000000-0000-0000-0000-000000000002',
        '41000000-0000-0000-0000-000000000002',
        'Which S3 storage class is designed for long-term archival with flexible retrieval options?',
        'single_choice',
        '["S3 Standard", "S3 One Zone-IA", "S3 Glacier Flexible Retrieval", "S3 Express One Zone"]',
        '["S3 Glacier Flexible Retrieval"]',
        'S3 Glacier Flexible Retrieval is intended for archive data that does not require immediate access.',
        3,
        '60000000-0000-0000-0000-000000000001',
        'published'
    )
ON CONFLICT DO NOTHING;

INSERT INTO assessment_questions (
    assessment_id,
    question_id,
    sequence_number,
    marks
)
VALUES
    (
        '61000000-0000-0000-0000-000000000001',
        '62000000-0000-0000-0000-000000000001',
        1,
        1
    ),
    (
        '61000000-0000-0000-0000-000000000001',
        '62000000-0000-0000-0000-000000000002',
        2,
        1
    )
ON CONFLICT DO NOTHING;

INSERT INTO assessment_attempts (
    id,
    assessment_id,
    learner_id,
    attempt_number,
    started_at,
    submitted_at,
    score,
    percentage,
    passed,
    status
)
VALUES
    (
        '63000000-0000-0000-0000-000000000001',
        '61000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000003',
        1,
        '2026-08-14T09:00:00Z',
        '2026-08-14T09:08:00Z',
        2,
        100,
        TRUE,
        'submitted'
    ),
    (
        '63000000-0000-0000-0000-000000000002',
        '61000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000004',
        1,
        '2026-08-14T10:00:00Z',
        '2026-08-14T10:09:00Z',
        0,
        0,
        FALSE,
        'submitted'
    )
ON CONFLICT DO NOTHING;

INSERT INTO question_responses (
    id,
    attempt_id,
    question_id,
    selected_answer_json,
    is_correct,
    marks_awarded,
    response_seconds
)
VALUES
    (
        '64000000-0000-0000-0000-000000000001',
        '63000000-0000-0000-0000-000000000001',
        '62000000-0000-0000-0000-000000000001',
        '["NAT gateway"]',
        TRUE,
        1,
        120
    ),
    (
        '64000000-0000-0000-0000-000000000002',
        '63000000-0000-0000-0000-000000000001',
        '62000000-0000-0000-0000-000000000002',
        '["S3 Glacier Flexible Retrieval"]',
        TRUE,
        1,
        140
    ),
    (
        '64000000-0000-0000-0000-000000000003',
        '63000000-0000-0000-0000-000000000002',
        '62000000-0000-0000-0000-000000000001',
        '["Internet gateway"]',
        FALSE,
        0,
        180
    ),
    (
        '64000000-0000-0000-0000-000000000004',
        '63000000-0000-0000-0000-000000000002',
        '62000000-0000-0000-0000-000000000002',
        '["S3 Standard"]',
        FALSE,
        0,
        210
    )
ON CONFLICT DO NOTHING;

INSERT INTO lab_tasks (
    id,
    course_id,
    topic_id,
    title,
    instructions,
    evidence_requirements,
    maximum_score,
    due_days,
    status
)
VALUES (
    '65000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001',
    '41000000-0000-0000-0000-000000000001',
    'Build a Secure Two-Tier VPC',
    'Create public and private subnets and document the routing path.',
    '{"required": ["architecture_diagram", "route_table_evidence"]}',
    100,
    7,
    'published'
)
ON CONFLICT DO NOTHING;

INSERT INTO lab_submissions (
    id,
    lab_task_id,
    learner_id,
    submission_number,
    submission_url,
    evidence_json,
    submitted_at,
    review_status,
    score,
    tutor_feedback,
    reviewed_by,
    reviewed_at
)
VALUES
    (
        '66000000-0000-0000-0000-000000000001',
        '65000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000003',
        1,
        'https://evidence.skillpulse.example/learner-one/vpc-lab',
        '{"architecture_diagram": true, "route_table_evidence": true}',
        '2026-08-18T12:00:00Z',
        'approved',
        90,
        'Clear architecture and correct private subnet routing.',
        '20000000-0000-0000-0000-000000000002',
        '2026-08-19T09:00:00Z'
    ),
    (
        '66000000-0000-0000-0000-000000000002',
        '65000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000004',
        1,
        'https://evidence.skillpulse.example/learner-two/vpc-lab',
        '{"architecture_diagram": true, "route_table_evidence": false}',
        '2026-08-18T13:00:00Z',
        'changes_requested',
        40,
        'Add the missing private route-table evidence.',
        '20000000-0000-0000-0000-000000000002',
        '2026-08-19T09:30:00Z'
    )
ON CONFLICT DO NOTHING;

INSERT INTO blockers (
    id,
    learner_id,
    cohort_id,
    topic_id,
    title,
    description,
    category,
    severity,
    status,
    assigned_tutor_id,
    opened_at,
    resolved_at,
    resolution_summary
)
VALUES
    (
        '70000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000004',
        '42000000-0000-0000-0000-000000000001',
        '41000000-0000-0000-0000-000000000001',
        'Private subnet routing confusion',
        'Learner cannot explain the NAT gateway route path.',
        'concept',
        'high',
        'assigned',
        '20000000-0000-0000-0000-000000000002',
        '2026-08-20T09:00:00Z',
        NULL,
        NULL
    ),
    (
        '70000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000003',
        '42000000-0000-0000-0000-000000000001',
        '41000000-0000-0000-0000-000000000002',
        'S3 storage-class selection',
        'Learner requested an additional storage decision exercise.',
        'practice',
        'medium',
        'resolved',
        '20000000-0000-0000-0000-000000000002',
        '2026-08-13T09:00:00Z',
        '2026-08-16T10:00:00Z',
        'Completed a comparison exercise and explained the selection criteria.'
    )
ON CONFLICT DO NOTHING;

INSERT INTO blocker_events (
    id,
    blocker_id,
    actor_id,
    event_type,
    old_status,
    new_status,
    comment,
    created_at
)
VALUES
    (
        '71000000-0000-0000-0000-000000000001',
        '70000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000002',
        'assigned',
        'open',
        'assigned',
        'Tutor assigned for focused routing support.',
        '2026-08-20T10:00:00Z'
    ),
    (
        '71000000-0000-0000-0000-000000000002',
        '70000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000002',
        'resolved',
        'assigned',
        'resolved',
        'Learner demonstrated the storage-class decision process.',
        '2026-08-16T10:00:00Z'
    )
ON CONFLICT DO NOTHING;

INSERT INTO tutor_interventions (
    id,
    learner_id,
    cohort_id,
    topic_id,
    blocker_id,
    intervention_type,
    action_taken,
    baseline_metric,
    baseline_value,
    follow_up_value,
    outcome,
    tutor_id,
    started_at,
    completed_at
)
VALUES
    (
        '72000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000003',
        '42000000-0000-0000-0000-000000000001',
        '41000000-0000-0000-0000-000000000002',
        '70000000-0000-0000-0000-000000000002',
        'targeted_practice',
        'Provided a storage-class scenario comparison exercise.',
        'topic_score',
        60,
        85,
        'improved',
        '20000000-0000-0000-0000-000000000002',
        '2026-08-13T10:00:00Z',
        '2026-08-16T10:00:00Z'
    ),
    (
        '72000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000004',
        '42000000-0000-0000-0000-000000000001',
        '41000000-0000-0000-0000-000000000001',
        '70000000-0000-0000-0000-000000000001',
        'one_to_one_support',
        'Scheduled a VPC route-table walkthrough.',
        'topic_score',
        0,
        NULL,
        'pending',
        '20000000-0000-0000-0000-000000000002',
        '2026-08-21T10:00:00Z',
        NULL
    )
ON CONFLICT DO NOTHING;

INSERT INTO readiness_models (
    id,
    organization_id,
    name,
    version,
    component_weights_json,
    readiness_threshold,
    minimum_mock_score,
    minimum_lab_completion,
    active_from,
    is_active
)
VALUES (
    '80000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'AWS SAA Pilot Readiness',
    '1.0',
    '{"quiz": 0.20, "mock": 0.30, "lab": 0.20, "attendance": 0.15, "blockers": 0.15}',
    75,
    70,
    80,
    '2026-08-01T00:00:00Z',
    TRUE
)
ON CONFLICT DO NOTHING;

INSERT INTO readiness_snapshots (
    id,
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
)
VALUES
    (
        '81000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000003',
        '42000000-0000-0000-0000-000000000001',
        '80000000-0000-0000-0000-000000000001',
        100,
        82,
        90,
        100,
        90,
        90.60,
        'ready',
        '{"strengths": ["attendance", "quiz", "lab"], "risk": "none"}',
        '2026-08-25T12:00:00Z'
    ),
    (
        '81000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000004',
        '42000000-0000-0000-0000-000000000001',
        '80000000-0000-0000-0000-000000000001',
        0,
        35,
        40,
        50,
        25,
        29.75,
        'developing',
        '{"strengths": [], "risk": "open blocker and low assessed competence"}',
        '2026-08-25T12:05:00Z'
    )
ON CONFLICT DO NOTHING;

INSERT INTO certificate_eligibility (
    id,
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
)
VALUES
    (
        '82000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000003',
        '42000000-0000-0000-0000-000000000001',
        '81000000-0000-0000-0000-000000000001',
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        '[]',
        '2026-08-25T12:10:00Z'
    ),
    (
        '82000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000004',
        '42000000-0000-0000-0000-000000000001',
        '81000000-0000-0000-0000-000000000002',
        FALSE,
        FALSE,
        FALSE,
        FALSE,
        FALSE,
        FALSE,
        '["attendance", "assignment", "lab", "mock_score", "open_blocker"]',
        '2026-08-25T12:15:00Z'
    )
ON CONFLICT DO NOTHING;
