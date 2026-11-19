"""Module assignments: learners submit a written answer, tutors review it."""

from uuid import UUID

from sqlalchemy import text

from skillpulse.db.connection import get_engine
from skillpulse.db.final_project_reviews import _TUTOR_SCOPE, TutorAccessDenied
from skillpulse.db.module_progress import _SCOPE_SQL, ModuleAccessDenied

__all__ = [
    "AssignmentConflict",
    "AssignmentNotFound",
    "ModuleAccessDenied",
    "SubmissionNotFound",
    "TutorAccessDenied",
    "all_assignments_approved",
    "list_assignment_submissions",
    "list_learner_assignments",
    "review_assignment_submission",
    "submit_assignment",
]


class AssignmentNotFound(Exception):
    """No published assignment with this id exists for the course."""


class AssignmentConflict(Exception):
    """The assignment cannot be submitted or reviewed in its current state."""


class SubmissionNotFound(Exception):
    """The submission is outside the requested cohort."""


_SUBMISSION_COLUMNS = """
    s.id AS submission_id,
    s.assignment_id,
    s.submission_number,
    s.answer_text,
    s.link_url,
    s.review_status::text AS review_status,
    s.tutor_feedback,
    s.reviewed_by,
    s.reviewed_at,
    s.submitted_at
"""

# The latest submission for each learner and assignment in a cohort.
_LATEST = """
    SELECT DISTINCT ON (s.assignment_id, s.learner_id) s.*
    FROM assignment_submissions AS s
    WHERE s.course_id = :course_id
      AND s.cohort_id = :cohort_id
    ORDER BY s.assignment_id, s.learner_id, s.submission_number DESC
"""

_LIST_LEARNER_ASSIGNMENTS = text(f"""
    WITH latest AS ({_LATEST})
    SELECT
        a.id AS assignment_id,
        a.topic_id,
        t.title AS module_title,
        t.sequence_number,
        a.title,
        a.instructions,
        {_SUBMISSION_COLUMNS.replace("s.assignment_id,", "")}
    FROM module_assignments AS a
    JOIN topics AS t ON t.id = a.topic_id
    LEFT JOIN latest AS s
      ON s.assignment_id = a.id
     AND s.learner_id = :learner_id
    WHERE a.course_id = :course_id
      AND a.status = 'published'
    ORDER BY t.sequence_number
""")

_ALL_APPROVED = text(f"""
    WITH latest AS ({_LATEST})
    SELECT
        COUNT(*) > 0
        AND COUNT(*) FILTER (WHERE s.review_status = 'approved') = COUNT(*)
    FROM module_assignments AS a
    LEFT JOIN latest AS s
      ON s.assignment_id = a.id
     AND s.learner_id = :learner_id
    WHERE a.course_id = :course_id
      AND a.status = 'published'
""")


def _parameters(organization_id, course_id, cohort_id, **extra):
    return {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        **extra,
    }


def _require_learner(connection, parameters, *, lock=False):
    sql = _SCOPE_SQL + (" FOR UPDATE OF cm" if lock else "")
    if connection.execute(text(sql), parameters).scalar_one_or_none() is None:
        raise ModuleAccessDenied()


def _require_tutor(connection, parameters):
    if connection.execute(_TUTOR_SCOPE, parameters).scalar_one_or_none() is None:
        raise TutorAccessDenied()


def _block_reason(review_status: str | None) -> str | None:
    if review_status == "submitted":
        return "Your answer is waiting for tutor review."
    if review_status == "approved":
        return "This assignment is already approved."
    return None


def _learner_view(row) -> dict:
    row = dict(row)
    latest = None
    if row["submission_id"] is not None:
        latest = {
            key: row[key]
            for key in (
                "submission_id",
                "submission_number",
                "answer_text",
                "link_url",
                "review_status",
                "tutor_feedback",
                "reviewed_at",
                "submitted_at",
            )
        }
    reason = _block_reason(latest["review_status"] if latest else None)
    return {
        "assignment_id": row["assignment_id"],
        "topic_id": row["topic_id"],
        "module_title": row["module_title"],
        "title": row["title"],
        "instructions": row["instructions"],
        "can_submit": reason is None,
        "submission_block_reason": reason,
        "latest_submission": latest,
    }


def list_learner_assignments(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
) -> list[dict]:
    """Return each published assignment with this learner's latest answer."""
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id=learner_id
    )
    with get_engine().begin() as connection:
        _require_learner(connection, parameters)
        rows = connection.execute(
            _LIST_LEARNER_ASSIGNMENTS, parameters
        ).mappings().all()
        return [_learner_view(row) for row in rows]


def submit_assignment(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    assignment_id: UUID,
    submission_id: UUID,
    answer_text: str,
    link_url: str | None,
) -> dict:
    """Save a learner's answer.

    Sending the same submission id twice with the same content returns the
    saved answer instead of creating a duplicate (safe to retry).
    """
    parameters = _parameters(
        organization_id,
        course_id,
        cohort_id,
        learner_id=learner_id,
        assignment_id=assignment_id,
        submission_id=submission_id,
        answer_text=answer_text,
        link_url=link_url,
    )

    with get_engine().begin() as connection:
        _require_learner(connection, parameters, lock=True)

        assignment = connection.execute(
            text("""
                SELECT id FROM module_assignments
                WHERE id = :assignment_id
                  AND course_id = :course_id
                  AND status = 'published'
                FOR SHARE
            """),
            parameters,
        ).scalar_one_or_none()
        if assignment is None:
            raise AssignmentNotFound()

        existing = connection.execute(
            text(f"""
                SELECT {_SUBMISSION_COLUMNS}, s.learner_id, s.cohort_id
                FROM assignment_submissions AS s
                WHERE s.id = :submission_id
            """),
            parameters,
        ).mappings().one_or_none()
        if existing is not None:
            same = (
                existing["learner_id"] == learner_id
                and existing["cohort_id"] == cohort_id
                and existing["assignment_id"] == assignment_id
                and existing["answer_text"] == answer_text
                and existing["link_url"] == link_url
            )
            if not same:
                raise AssignmentConflict(
                    "This submission identifier was used for different content."
                )
            return {
                key: value
                for key, value in existing.items()
                if key not in {"learner_id", "cohort_id", "reviewed_by"}
            }

        latest = connection.execute(
            text("""
                SELECT review_status::text, submission_number
                FROM assignment_submissions
                WHERE assignment_id = :assignment_id
                  AND cohort_id = :cohort_id
                  AND learner_id = :learner_id
                ORDER BY submission_number DESC
                LIMIT 1
            """),
            parameters,
        ).one_or_none()

        reason = _block_reason(latest[0] if latest else None)
        if reason is not None:
            raise AssignmentConflict(reason)

        parameters["submission_number"] = (latest[1] if latest else 0) + 1
        row = connection.execute(
            text(f"""
                INSERT INTO assignment_submissions AS s (
                    id, assignment_id, course_id, cohort_id, learner_id,
                    submission_number, answer_text, link_url
                )
                VALUES (
                    :submission_id, :assignment_id, :course_id, :cohort_id,
                    :learner_id, :submission_number, :answer_text, :link_url
                )
                RETURNING {_SUBMISSION_COLUMNS}
            """),
            parameters,
        ).mappings().one()
        result = dict(row)
        result.pop("reviewed_by", None)
        return result


_TUTOR_SELECT = f"""
    SELECT
        {_SUBMISSION_COLUMNS},
        s.learner_id,
        learner.full_name AS learner_name,
        a.title AS assignment_title,
        t.title AS module_title,
        NOT EXISTS (
            SELECT 1 FROM assignment_submissions AS newer
            WHERE newer.assignment_id = s.assignment_id
              AND newer.cohort_id = s.cohort_id
              AND newer.learner_id = s.learner_id
              AND newer.submission_number > s.submission_number
        ) AS is_latest
    FROM assignment_submissions AS s
    JOIN module_assignments AS a ON a.id = s.assignment_id
    JOIN topics AS t ON t.id = a.topic_id
    JOIN users AS learner ON learner.id = s.learner_id
    WHERE s.course_id = :course_id
      AND s.cohort_id = :cohort_id
"""


def list_assignment_submissions(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    tutor_id: UUID,
    review_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return a cohort's submissions for its tutor, oldest waiting first."""
    parameters = _parameters(
        organization_id,
        course_id,
        cohort_id,
        tutor_id=tutor_id,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )
    status_filter = (
        " AND s.review_status = CAST(:review_status AS lab_review_status)"
        if review_status
        else ""
    )

    with get_engine().begin() as connection:
        _require_tutor(connection, parameters)
        total = connection.execute(
            text(
                "SELECT COUNT(*) FROM assignment_submissions AS s"
                " WHERE s.course_id = :course_id"
                " AND s.cohort_id = :cohort_id" + status_filter
            ),
            parameters,
        ).scalar_one()
        rows = connection.execute(
            text(
                _TUTOR_SELECT + status_filter +
                " ORDER BY (s.review_status = 'submitted') DESC,"
                " s.submitted_at ASC, s.id"
                " LIMIT :limit OFFSET :offset"
            ),
            parameters,
        ).mappings().all()
        return [dict(row) for row in rows], total


def review_assignment_submission(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    tutor_id: UUID,
    submission_id: UUID,
    review_status: str,
    tutor_feedback: str,
) -> dict:
    """Approve a learner's latest answer or send it back for changes."""
    if review_status not in {"approved", "changes_requested"}:
        raise AssignmentConflict("Choose approve or request changes.")

    parameters = _parameters(
        organization_id,
        course_id,
        cohort_id,
        tutor_id=tutor_id,
        submission_id=submission_id,
        review_status=review_status,
        tutor_feedback=tutor_feedback,
    )

    with get_engine().begin() as connection:
        _require_tutor(connection, parameters)

        submission = connection.execute(
            text(_TUTOR_SELECT + " AND s.id = :submission_id FOR UPDATE OF s"),
            parameters,
        ).mappings().one_or_none()
        if submission is None:
            raise SubmissionNotFound()
        if not submission["is_latest"]:
            raise AssignmentConflict("Review the learner's latest answer.")
        if submission["review_status"] != "submitted":
            raise AssignmentConflict("This answer has already been reviewed.")

        connection.execute(
            text("""
                UPDATE assignment_submissions
                SET review_status = CAST(:review_status AS lab_review_status),
                    tutor_feedback = :tutor_feedback,
                    reviewed_by = :tutor_id,
                    reviewed_at = NOW()
                WHERE id = :submission_id
            """),
            parameters,
        )
        updated = connection.execute(
            text(_TUTOR_SELECT + " AND s.id = :submission_id"),
            parameters,
        ).mappings().one()
        return dict(updated)


def all_assignments_approved(connection, parameters) -> bool:
    """True when every published assignment has an approved latest answer.

    Used by certificate eligibility inside its own transaction. A course with
    no published assignments does not meet the requirement.
    """
    return bool(connection.execute(_ALL_APPROVED, parameters).scalar_one())
