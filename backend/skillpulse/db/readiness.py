"""Organisation-scoped learner readiness queries."""

import json
from uuid import UUID

from skillpulse.core.readiness import calculate_readiness
from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from skillpulse.db.connection import get_engine


_GET_READINESS_INPUTS = text(
    """
    WITH target_cohort AS (
        SELECT
            h.id AS cohort_id,
            h.course_id,
            c.organization_id,
            cm.enrolled_at
        FROM cohorts AS h
        JOIN courses AS c
            ON c.id = h.course_id
        JOIN cohort_memberships AS cm
            ON cm.cohort_id = h.id
        WHERE
            c.organization_id = :organization_id
            AND c.id = :course_id
            AND h.id = :cohort_id
            AND cm.user_id = :learner_id
            AND cm.cohort_role::TEXT = 'learner'
            AND cm.status::TEXT = 'active'
    ),
    active_model AS (
        SELECT
            rm.id,
            rm.component_weights_json,
            rm.readiness_threshold,
            rm.minimum_mock_score,
            rm.minimum_lab_completion
        FROM readiness_models AS rm
        JOIN target_cohort AS t
            ON t.organization_id = rm.organization_id
        WHERE
            rm.is_active = TRUE
            AND rm.active_from <= CURRENT_TIMESTAMP
            AND (
                rm.active_to IS NULL
                OR rm.active_to >= CURRENT_TIMESTAMP
            )
        ORDER BY rm.active_from DESC
        LIMIT 1
    ),
    quiz_component AS (
        SELECT COALESCE(
            AVG(COALESCE(latest.percentage, 0)),
            0
        ) AS score
        FROM target_cohort AS t
        JOIN assessments AS a
            ON a.course_id = t.course_id
        LEFT JOIN LATERAL (
            SELECT aa.percentage
            FROM assessment_attempts AS aa
            WHERE
                aa.assessment_id = a.id
                AND aa.learner_id = :learner_id
                AND aa.status::TEXT = 'submitted'
            ORDER BY aa.submitted_at DESC, aa.attempt_number DESC
            LIMIT 1
        ) AS latest ON TRUE
        WHERE
            a.assessment_type::TEXT = 'quiz'
            AND a.status::TEXT = 'published'
    ),
    mock_component AS (
        SELECT COALESCE(
            AVG(COALESCE(latest.percentage, 0)),
            0
        ) AS score
        FROM target_cohort AS t
        JOIN assessments AS a
            ON a.course_id = t.course_id
        LEFT JOIN LATERAL (
            SELECT aa.percentage
            FROM assessment_attempts AS aa
            WHERE
                aa.assessment_id = a.id
                AND aa.learner_id = :learner_id
                AND aa.status::TEXT = 'submitted'
            ORDER BY aa.submitted_at DESC
            LIMIT 1
        ) AS latest ON TRUE
        WHERE
            a.assessment_type::TEXT = 'mock_exam'
            AND a.status::TEXT = 'published'
    ),
    approved_labs AS (
        SELECT DISTINCT ls.lab_task_id
        FROM lab_submissions AS ls
        WHERE
            ls.learner_id = :learner_id
            AND ls.review_status::TEXT = 'approved'
    ),
    lab_component AS (
        SELECT
            CASE
                WHEN COUNT(*) = 0 THEN 0
                ELSE
                    COUNT(al.lab_task_id)::NUMERIC * 100
                    / COUNT(*)
            END AS score
        FROM target_cohort AS t
        JOIN lab_tasks AS lt
            ON lt.course_id = t.course_id
            AND lt.status::TEXT = 'published'
        LEFT JOIN approved_labs AS al
            ON al.lab_task_id = lt.id
    ),

    attendance_component AS (
        SELECT
            CASE
                WHEN COUNT(*) FILTER (
                    WHERE ar.attendance_status::TEXT
                        IS DISTINCT FROM 'excused'
                ) = 0 THEN 0
                ELSE
                    COUNT(*) FILTER (
                        WHERE ar.attendance_status::TEXT
                            IN ('present', 'late')
                    )::NUMERIC * 100
                    / COUNT(*) FILTER (
                        WHERE ar.attendance_status::TEXT
                            IS DISTINCT FROM 'excused'
                    )
            END AS score
        FROM target_cohort AS t
        JOIN class_sessions AS cs
            ON cs.cohort_id = t.cohort_id
            AND cs.status::TEXT = 'completed'
            AND cs.scheduled_end <= CURRENT_TIMESTAMP
            AND cs.scheduled_start >= t.enrolled_at
        LEFT JOIN attendance_records AS ar
            ON ar.session_id = cs.id
            AND ar.learner_id = :learner_id
    ),





    blocker_component AS (
        SELECT GREATEST(
            0::NUMERIC,
            100::NUMERIC - LEAST(
                100::NUMERIC,
                COALESCE(
                    SUM(
                        CASE
                            WHEN b.status::TEXT IN (
                                'open',
                                'assigned',
                                'waiting_student'
                            )
                            THEN
                                CASE b.severity::TEXT
                                    WHEN 'low' THEN 5
                                    WHEN 'medium' THEN 10
                                    WHEN 'high' THEN 20
                                    WHEN 'critical' THEN 30
                                    ELSE 0
                                END
                            ELSE 0
                        END
                    ),
                    0
                )
            )
        ) AS score
        FROM target_cohort AS t
        JOIN blockers AS b
            ON b.cohort_id = t.cohort_id
            AND b.learner_id = :learner_id
    )
    SELECT
        m.id AS readiness_model_id,
        m.component_weights_json,
        m.readiness_threshold,
        m.minimum_mock_score,
        m.minimum_lab_completion,
        q.score AS quiz_component,
        mock.score AS mock_component,
        lab.score AS lab_component,
        attendance.score AS attendance_component,
        blocker.score AS blocker_component
    FROM active_model AS m
    CROSS JOIN quiz_component AS q
    CROSS JOIN mock_component AS mock
    CROSS JOIN lab_component AS lab
    CROSS JOIN attendance_component AS attendance
    CROSS JOIN blocker_component AS blocker
    """
)


def get_readiness_inputs(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
) -> RowMapping | None:
    """Return scoped readiness inputs and the active organisation model."""
    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": learner_id,
    }
    with get_engine().connect() as connection:
        return (
            connection.execute(_GET_READINESS_INPUTS, parameters)
            .mappings()
            .one_or_none()
        )


def create_readiness_snapshot(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
) -> RowMapping | None:
    """Calculate and save a scoped learner readiness snapshot."""
    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": learner_id,
    }

    with get_engine().begin() as connection:
        inputs = (
            connection.execute(_GET_READINESS_INPUTS, parameters)
            .mappings()
            .one_or_none()
        )

        if inputs is None:
            return None

        column_mapping = {
            "quiz": "quiz_component",
            "mock": "mock_component",
            "lab": "lab_component",
            "attendance": "attendance_component",
            "blockers": "blocker_component",
        }
        components = {
            name: float(inputs[column])
            for name, column in column_mapping.items()
        }
        weights = {
            name: float(value)
            for name, value in inputs["component_weights_json"].items()
        }
        thresholds = {
            name: float(inputs[name])
            for name in (
                "readiness_threshold",
                "minimum_mock_score",
                "minimum_lab_completion",
            )
        }

        result = calculate_readiness(
            components=components,
            weights=weights,
            **thresholds,
        )

        explanation = {
            **result["explanation_json"],
            "thresholds": thresholds,
        }

        snapshot_parameters = {
            "learner_id": learner_id,
            "cohort_id": cohort_id,
            "readiness_model_id": inputs["readiness_model_id"],
            **{
                column: components[name]
                for name, column in column_mapping.items()
            },
            "overall_score": result["overall_score"],
            "readiness_level": result["readiness_level"],
            "explanation_json": json.dumps(explanation, allow_nan=False),
        }

        return (
            connection.execute(
                text("""
                    INSERT INTO readiness_snapshots (
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
                        explanation_json
                    )
                    VALUES (
                        :learner_id,
                        :cohort_id,
                        :readiness_model_id,
                        :quiz_component,
                        :mock_component,
                        :lab_component,
                        :attendance_component,
                        :blocker_component,
                        :overall_score,
                        CAST(:readiness_level AS readiness_level),
                        CAST(:explanation_json AS JSONB)
                    )
                    RETURNING *
                """),
                snapshot_parameters,
            )
            .mappings()
            .one()
        )
def list_readiness_snapshots(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[RowMapping]:
    """Return scoped snapshot history, newest first."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if offset < 0:
        raise ValueError("offset must not be negative")

    query = text("""
        SELECT snapshot.*
        FROM readiness_snapshots AS snapshot
        JOIN cohorts AS cohort
            ON cohort.id = snapshot.cohort_id
        JOIN courses AS course
            ON course.id = cohort.course_id
        JOIN readiness_models AS model
            ON model.id = snapshot.readiness_model_id
            AND model.organization_id = course.organization_id
        JOIN cohort_memberships AS membership
            ON membership.cohort_id = cohort.id
            AND membership.user_id = snapshot.learner_id
        WHERE course.organization_id = :organization_id
            AND course.id = :course_id
            AND cohort.id = :cohort_id
            AND snapshot.learner_id = :learner_id
            AND membership.status::TEXT = 'active'
            AND membership.cohort_role::TEXT = 'learner'
        ORDER BY snapshot.calculated_at DESC, snapshot.id DESC
        LIMIT :limit OFFSET :offset
    """)

    with get_engine().connect() as connection:
        return list(
            connection.execute(
                query,
                {
                    "organization_id": organization_id,
                    "course_id": course_id,
                    "cohort_id": cohort_id,
                    "learner_id": learner_id,
                    "limit": limit,
                    "offset": offset,
                },
            ).mappings().all()
        )
