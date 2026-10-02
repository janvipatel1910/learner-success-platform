"""Scoped final project details and learner submissions."""

import json
from uuid import UUID

from sqlalchemy import text

from skillpulse.db.connection import get_engine
from skillpulse.db.module_progress import ModuleAccessDenied, _SCOPE_SQL


class FinalProjectNotFound(Exception):
    """No published final project exists for this course."""


class FinalProjectConflict(Exception):
    """The project cannot be submitted in its current state."""


_SUBMISSION_SELECT = """
    SELECT
        ls.id AS submission_id,
        ls.submission_number,
        ls.submission_url,
        COALESCE(ls.evidence_json->>'note', '') AS note,
        ls.review_status::text AS review_status,
        ls.score,
        ls.tutor_feedback,
        ls.reviewed_by,
        ls.reviewed_at,
        ls.submitted_at
    FROM final_project_submissions AS fs
    JOIN lab_submissions AS ls
      ON ls.id = fs.submission_id
     AND ls.learner_id = fs.learner_id
     AND ls.lab_task_id = fs.lab_task_id
    WHERE fs.course_id = :course_id
      AND fs.cohort_id = :cohort_id
      AND fs.learner_id = :learner_id
      AND fs.lab_task_id = :lab_task_id
"""


def _parameters(organization_id, course_id, cohort_id, learner_id):
    return {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": learner_id,
    }


def _require_membership(connection, parameters, *, lock=False):
    sql = _SCOPE_SQL + (" FOR UPDATE OF cm" if lock else "")
    membership = connection.execute(
        text(sql), parameters
    ).scalar_one_or_none()

    if membership is None:
        raise ModuleAccessDenied()


def _project(connection, parameters):
    project = connection.execute(
        text("""
            SELECT
                l.id AS lab_task_id,
                l.title,
                l.instructions,
                l.evidence_requirements,
                l.maximum_score
            FROM course_final_projects AS p
            JOIN lab_tasks AS l
              ON l.id = p.lab_task_id
             AND l.course_id = p.course_id
            WHERE p.course_id = :course_id
              AND l.status = 'published'
            FOR SHARE OF p, l
        """),
        parameters,
    ).mappings().one_or_none()

    if project is None:
        raise FinalProjectNotFound()

    return dict(project)


def _module_counts(connection, parameters):
    return connection.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE mp.status = 'completed'
                ) AS completed
            FROM topics AS t
            LEFT JOIN module_progress AS mp
              ON mp.topic_id = t.id
             AND mp.cohort_id = :cohort_id
             AND mp.learner_id = :learner_id
            WHERE t.course_id = :course_id
        """),
        parameters,
    ).mappings().one()


def _latest_submission(connection, parameters):
    row = connection.execute(
        text(
            _SUBMISSION_SELECT +
            " ORDER BY ls.submission_number DESC, ls.id DESC LIMIT 1"
        ),
        parameters,
    ).mappings().one_or_none()

    return dict(row) if row is not None else None


def _block_reason(counts, latest):
    if counts["total"] == 0:
        return "No modules are configured for this course."

    if counts["completed"] != counts["total"]:
        return "Complete all modules before submitting the final project."

    if latest is not None:
        if latest["review_status"] in {"submitted", "under_review"}:
            return "Your project is awaiting tutor review."
        if latest["review_status"] == "approved":
            return "Your final project is already approved."

    return None


def get_learner_final_project(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
):
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id
    )

    with get_engine().begin() as connection:
        _require_membership(connection, parameters)
        project = _project(connection, parameters)
        parameters["lab_task_id"] = project["lab_task_id"]

        counts = _module_counts(connection, parameters)
        latest = _latest_submission(connection, parameters)
        reason = _block_reason(counts, latest)

        return {
            **project,
            "modules_completed": counts["completed"],
            "modules_total": counts["total"],
            "can_submit": reason is None,
            "submission_block_reason": reason,
            "latest_submission": latest,
        }


def submit_learner_final_project(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    submission_id: UUID,
    submission_url: str,
    note: str,
):
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id
    )
    parameters.update({
        "submission_id": submission_id,
        "submission_url": submission_url,
        "note": note,
    })

    with get_engine().begin() as connection:
        _require_membership(connection, parameters, lock=True)

        # Serialize submission numbering across this learner's cohorts.
        connection.execute(
            text("SELECT id FROM users WHERE id = :learner_id FOR UPDATE"),
            parameters,
        ).scalar_one()

        project = _project(connection, parameters)
        parameters["lab_task_id"] = project["lab_task_id"]

        existing = connection.execute(
            text(_SUBMISSION_SELECT + " AND ls.id = :submission_id"),
            parameters,
        ).mappings().one_or_none()

        if existing is not None:
            if (
                existing["submission_url"] != submission_url
                or existing["note"] != note
            ):
                raise FinalProjectConflict(
                    "This submission identifier was used for different content."
                )
            return dict(existing)

        identifier_used = connection.execute(
            text("SELECT 1 FROM lab_submissions WHERE id = :submission_id"),
            parameters,
        ).scalar_one_or_none()

        if identifier_used is not None:
            raise FinalProjectConflict(
                "Submission identifier is already in use."
            )

        counts = _module_counts(connection, parameters)
        latest = _latest_submission(connection, parameters)
        reason = _block_reason(counts, latest)

        if reason is not None:
            raise FinalProjectConflict(reason)

        submission_number = connection.execute(
            text("""
                SELECT COALESCE(MAX(submission_number), 0) + 1
                FROM lab_submissions
                WHERE lab_task_id = :lab_task_id
                  AND learner_id = :learner_id
            """),
            parameters,
        ).scalar_one()

        parameters.update({
            "submission_number": submission_number,
            "evidence_json": json.dumps({"note": note}),
        })

        connection.execute(
            text("""
                INSERT INTO lab_submissions (
                    id, lab_task_id, learner_id, submission_number,
                    submission_url, evidence_json, review_status
                )
                VALUES (
                    :submission_id, :lab_task_id, :learner_id,
                    :submission_number, :submission_url,
                    CAST(:evidence_json AS jsonb), 'submitted'
                )
            """),
            parameters,
        )

        connection.execute(
            text("""
                INSERT INTO final_project_submissions (
                    submission_id, course_id, cohort_id,
                    lab_task_id, learner_id
                )
                VALUES (
                    :submission_id, :course_id, :cohort_id,
                    :lab_task_id, :learner_id
                )
            """),
            parameters,
        )

        row = connection.execute(
            text(_SUBMISSION_SELECT + " AND ls.id = :submission_id"),
            parameters,
        ).mappings().one()

        return dict(row)
