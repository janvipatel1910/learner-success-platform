"""Scoped learner module progression."""

from uuid import UUID

from sqlalchemy import text

from skillpulse.db.connection import get_engine


class ModuleAccessDenied(Exception):
    """The learner has no active membership in this scoped cohort."""


class ModuleNotFound(Exception):
    """The requested topic does not belong to this course."""


class ModuleLocked(Exception):
    """Earlier modules must be completed first."""


_SCOPE_SQL = """
    SELECT cm.id
    FROM cohort_memberships AS cm
    JOIN cohorts AS co ON co.id = cm.cohort_id
    JOIN courses AS c ON c.id = co.course_id
    WHERE c.organization_id = :organization_id
      AND c.id = :course_id
      AND co.id = :cohort_id
      AND cm.user_id = :learner_id
      AND cm.cohort_role = 'learner'
      AND cm.status = 'active'
"""

_LIST_MODULES = text(
    """
    SELECT
        t.id AS topic_id,
        t.title,
        t.sequence_number,
        t.exam_domain,
        t.expected_hours,
        CASE
            WHEN mp.status = 'completed' THEN 'completed'
            WHEN EXISTS (
                SELECT 1
                FROM topics AS earlier
                WHERE earlier.course_id = t.course_id
                  AND earlier.sequence_number < t.sequence_number
                  AND NOT EXISTS (
                      SELECT 1
                      FROM module_progress AS previous_progress
                      WHERE previous_progress.topic_id = earlier.id
                        AND previous_progress.cohort_id = :cohort_id
                        AND previous_progress.learner_id = :learner_id
                        AND previous_progress.status = 'completed'
                  )
            ) THEN 'locked'
            WHEN mp.status = 'in_progress' THEN 'in_progress'
            ELSE 'available'
        END AS status,
        mp.started_at,
        mp.completed_at
    FROM topics AS t
    LEFT JOIN module_progress AS mp
        ON mp.topic_id = t.id
       AND mp.cohort_id = :cohort_id
       AND mp.learner_id = :learner_id
    WHERE t.course_id = :course_id
    ORDER BY t.sequence_number, t.id
    """
)

_START_MODULE = text(
    """
    INSERT INTO module_progress (
        cohort_id,
        learner_id,
        topic_id
    )
    VALUES (
        :cohort_id,
        :learner_id,
        :topic_id
    )
    ON CONFLICT (cohort_id, learner_id, topic_id)
    DO NOTHING
    """
)


def _parameters(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
) -> dict[str, UUID]:
    return {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": learner_id,
    }


def list_learner_modules(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
) -> list[dict[str, object]]:
    """List course modules with this learner's progression state."""
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id
    )

    with get_engine().begin() as connection:
        membership = connection.execute(
            text(_SCOPE_SQL), parameters
        ).scalar_one_or_none()

        if membership is None:
            raise ModuleAccessDenied()

        rows = connection.execute(
            _LIST_MODULES, parameters
        ).mappings().all()

        return [dict(row) for row in rows]


def start_learner_module(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    topic_id: UUID,
) -> dict[str, object]:
    """Start an unlocked module without resetting existing progress."""
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id
    )
    parameters["topic_id"] = topic_id

    with get_engine().begin() as connection:
        # Serialize progression writes for this cohort membership.
        membership = connection.execute(
            text(_SCOPE_SQL + " FOR UPDATE OF cm"),
            parameters,
        ).scalar_one_or_none()

        if membership is None:
            raise ModuleAccessDenied()

        modules = connection.execute(
            _LIST_MODULES, parameters
        ).mappings().all()

        module = next(
            (row for row in modules if row["topic_id"] == topic_id),
            None,
        )

        if module is None:
            raise ModuleNotFound()

        if module["status"] == "locked":
            raise ModuleLocked()

        if module["status"] in {"in_progress", "completed"}:
            return dict(module)

        connection.execute(_START_MODULE, parameters)

        updated_modules = connection.execute(
            _LIST_MODULES, parameters
        ).mappings().all()

        return next(
            dict(row)
            for row in updated_modules
            if row["topic_id"] == topic_id
        )
