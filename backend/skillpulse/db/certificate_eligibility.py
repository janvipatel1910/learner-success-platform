"""Evaluate and save certificate eligibility for one learner and cohort."""

import json
from uuid import UUID

from sqlalchemy import text

from skillpulse.db.connection import get_engine
from skillpulse.db.module_progress import _SCOPE_SQL


class CertificateAccessDenied(Exception):
    """The learner is not active in this organisation, course and cohort."""


_MODULE_CHECKS_MET = text("""
    SELECT
        COUNT(*) > 0
        AND COUNT(*) FILTER (
            WHERE mp.status = 'completed'
              AND ma.assessment_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM module_assessment_attempts AS maa
                  JOIN assessment_attempts AS aa
                    ON aa.id = maa.attempt_id
                   AND aa.learner_id = mp.learner_id
                  JOIN assessments AS a
                    ON a.id = aa.assessment_id
                  WHERE maa.module_progress_id = mp.id
                    AND a.id = ma.assessment_id
                    AND aa.status = 'submitted'
                    AND aa.passed IS TRUE
                    AND aa.percentage >= a.pass_percentage
              )
        ) = COUNT(*) AS met
    FROM topics AS t
    LEFT JOIN module_progress AS mp
      ON mp.topic_id = t.id
     AND mp.cohort_id = :cohort_id
     AND mp.learner_id = :learner_id
    LEFT JOIN module_assessments AS ma
      ON ma.topic_id = t.id
     AND ma.course_id = t.course_id
    WHERE t.course_id = :course_id
""")

_FINAL_PROJECT_MET = text("""
    SELECT EXISTS (
        SELECT 1
        FROM course_final_projects AS fp
        JOIN lab_tasks AS task
          ON task.id = fp.lab_task_id
         AND task.course_id = fp.course_id
        JOIN LATERAL (
            SELECT
                submission.review_status::text AS review_status,
                submission.score
            FROM final_project_submissions AS fs
            JOIN lab_submissions AS submission
              ON submission.id = fs.submission_id
             AND submission.lab_task_id = fs.lab_task_id
             AND submission.learner_id = fs.learner_id
            WHERE fs.course_id = :course_id
              AND fs.cohort_id = :cohort_id
              AND fs.learner_id = :learner_id
              AND fs.lab_task_id = fp.lab_task_id
            ORDER BY submission.submission_number DESC,
                     submission.submitted_at DESC
            LIMIT 1
        ) AS latest ON TRUE
        WHERE fp.course_id = :course_id
          AND task.status = 'published'
          AND latest.review_status = 'approved'
          AND latest.score IS NOT NULL
          AND latest.score / NULLIF(task.maximum_score, 0) * 100
              >= fp.minimum_passing_percentage
    )
""")


def evaluate_certificate_eligibility(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
) -> dict[str, object]:
    """Save a fresh eligibility evaluation using current module and project data."""
    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": learner_id,
    }

    with get_engine().begin() as connection:
        member = connection.execute(
            text(_SCOPE_SQL), parameters
        ).scalar_one_or_none()
        if member is None:
            raise CertificateAccessDenied()

        previous = connection.execute(
            text("""
                SELECT
                    attendance_met,
                    assignment_met,
                    lab_met,
                    mock_score_met,
                    blockers_cleared,
                    readiness_snapshot_id
                FROM certificate_eligibility
                WHERE learner_id = :learner_id
                  AND cohort_id = :cohort_id
                ORDER BY evaluated_at DESC
                LIMIT 1
            """),
            parameters,
        ).mappings().one_or_none()

        existing_gates = {
            name: bool(previous[name]) if previous is not None else False
            for name in (
                "attendance_met",
                "assignment_met",
                "lab_met",
                "mock_score_met",
                "blockers_cleared",
            )
        }
        module_checks_met = bool(
            connection.execute(_MODULE_CHECKS_MET, parameters).scalar_one()
        )
        final_project_met = bool(
            connection.execute(_FINAL_PROJECT_MET, parameters).scalar_one()
        )

        gates = {
            **existing_gates,
            "module_checks_met": module_checks_met,
            "final_project_met": final_project_met,
        }
        missing = [name for name, met in gates.items() if not met]
        readiness_snapshot_id = (
            previous["readiness_snapshot_id"]
            if previous is not None
            else None
        )

        row = connection.execute(
            text("""
                INSERT INTO certificate_eligibility (
                    learner_id,
                    cohort_id,
                    readiness_snapshot_id,
                    attendance_met,
                    assignment_met,
                    lab_met,
                    mock_score_met,
                    blockers_cleared,
                    module_checks_met,
                    final_project_met,
                    is_eligible,
                    missing_requirements_json
                )
                VALUES (
                    :learner_id,
                    :cohort_id,
                    :readiness_snapshot_id,
                    :attendance_met,
                    :assignment_met,
                    :lab_met,
                    :mock_score_met,
                    :blockers_cleared,
                    :module_checks_met,
                    :final_project_met,
                    :is_eligible,
                    CAST(:missing_requirements_json AS jsonb)
                )
                RETURNING *
            """),
            {
                **parameters,
                **gates,
                "readiness_snapshot_id": readiness_snapshot_id,
                "is_eligible": not missing,
                "missing_requirements_json": json.dumps(missing),
            },
        ).mappings().one()

        return dict(row)
