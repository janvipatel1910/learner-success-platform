"""Assigned-tutor final project review operations."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import text

from skillpulse.db.connection import get_engine


class TutorAccessDenied(Exception):
    """The actor is not an active assigned tutor."""


class SubmissionNotFound(Exception):
    """The submission is outside the requested scope."""


class ReviewConflict(Exception):
    """The submission is no longer available for this review."""


class InvalidReview(ValueError):
    """Review values do not meet the project rules."""


_TUTOR_SCOPE = text("""
    SELECT cm.id
    FROM cohort_memberships AS cm
    JOIN cohorts AS co ON co.id = cm.cohort_id
    JOIN courses AS c ON c.id = co.course_id
    JOIN users AS u ON u.id = cm.user_id
    WHERE c.organization_id = :organization_id
      AND c.id = :course_id
      AND co.id = :cohort_id
      AND cm.user_id = :tutor_id
      AND cm.cohort_role = 'tutor'
      AND cm.status = 'active'
      AND u.status = 'active'
      AND EXISTS (
          SELECT 1
          FROM organization_memberships AS om
          WHERE om.organization_id = c.organization_id
            AND om.user_id = cm.user_id
            AND om.role = 'tutor'
            AND om.status = 'active'
      )
    FOR SHARE OF cm, u
""")

_SCOPED_SUBMISSIONS = """
    FROM final_project_submissions AS fs
    JOIN lab_submissions AS ls
      ON ls.id = fs.submission_id
     AND ls.lab_task_id = fs.lab_task_id
     AND ls.learner_id = fs.learner_id
    JOIN lab_tasks AS l
      ON l.id = fs.lab_task_id
     AND l.course_id = fs.course_id
    JOIN users AS learner ON learner.id = fs.learner_id
    WHERE fs.course_id = :course_id
      AND fs.cohort_id = :cohort_id
"""

_SELECT_SUBMISSIONS = """
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
        ls.submitted_at,
        fs.learner_id,
        learner.full_name AS learner_name,
        l.title AS project_title,
        l.maximum_score
""" + _SCOPED_SUBMISSIONS


def _parameters(organization_id, course_id, cohort_id, tutor_id):
    return {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "tutor_id": tutor_id,
    }


def _require_tutor(connection, parameters):
    membership = connection.execute(
        _TUTOR_SCOPE, parameters
    ).scalar_one_or_none()
    if membership is None:
        raise TutorAccessDenied()


def list_project_submissions(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    tutor_id: UUID,
    limit: int = 20,
    offset: int = 0,
):
    parameters = _parameters(
        organization_id, course_id, cohort_id, tutor_id
    )
    parameters.update({"limit": limit, "offset": offset})

    with get_engine().begin() as connection:
        _require_tutor(connection, parameters)

        total = connection.execute(
            text("SELECT COUNT(*) " + _SCOPED_SUBMISSIONS),
            parameters,
        ).scalar_one()

        rows = connection.execute(
            text(
                _SELECT_SUBMISSIONS +
                " ORDER BY ls.submitted_at DESC, ls.id DESC"
                " LIMIT :limit OFFSET :offset"
            ),
            parameters,
        ).mappings().all()

        return [dict(row) for row in rows], total


def review_project_submission(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    tutor_id: UUID,
    submission_id: UUID,
    expected_review_status: str,
    review_status: str,
    score: Decimal | None,
    tutor_feedback: str,
):
    parameters = _parameters(
        organization_id, course_id, cohort_id, tutor_id
    )
    parameters["submission_id"] = submission_id

    with get_engine().begin() as connection:
        _require_tutor(connection, parameters)

        submission = connection.execute(
            text(
                _SELECT_SUBMISSIONS +
                " AND ls.id = :submission_id FOR UPDATE OF ls"
            ),
            parameters,
        ).mappings().one_or_none()

        if submission is None:
            raise SubmissionNotFound()

        current_status = submission["review_status"]

        if current_status not in {"submitted", "under_review"}:
            raise ReviewConflict("This submission already has a final review.")

        if current_status != expected_review_status:
            raise ReviewConflict(
                "The review status changed. Refresh before reviewing."
            )

        allowed = {
            "submitted": {
                "under_review", "changes_requested", "approved", "rejected"
            },
            "under_review": {
                "changes_requested", "approved", "rejected"
            },
        }
        if review_status not in allowed[current_status]:
            raise ReviewConflict("This review transition is not allowed.")

        newer_exists = connection.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM final_project_submissions AS newer_fs
                    JOIN lab_submissions AS newer
                      ON newer.id = newer_fs.submission_id
                    JOIN final_project_submissions AS current_fs
                      ON current_fs.submission_id = :submission_id
                    JOIN lab_submissions AS current_submission
                      ON current_submission.id = current_fs.submission_id
                    WHERE newer_fs.cohort_id = current_fs.cohort_id
                      AND newer_fs.learner_id = current_fs.learner_id
                      AND newer_fs.lab_task_id = current_fs.lab_task_id
                      AND newer.submission_number >
                          current_submission.submission_number
                )
            """),
            parameters,
        ).scalar_one()

        if newer_exists:
            raise ReviewConflict("Review the learner's latest submission.")

        if review_status == "approved" and score is None:
            raise InvalidReview("An approved project requires a score.")

        if review_status == "under_review" and score is not None:
            raise InvalidReview("Record a score with the final review.")

        if score is not None:
            if (
                not score.is_finite()
                or score < 0
                or score > submission["maximum_score"]
            ):
                raise InvalidReview(
                    "Score must be between zero and the project's maximum."
                )

        feedback = tutor_feedback.strip()
        if not 10 <= len(feedback) <= 5000:
            raise InvalidReview("Feedback must contain 10 to 5000 characters.")

        parameters.update({
            "review_status": review_status,
            "score": score,
            "tutor_feedback": feedback,
        })

        connection.execute(
            text("""
                UPDATE lab_submissions
                SET review_status = CAST(:review_status AS lab_review_status),
                    score = :score,
                    tutor_feedback = :tutor_feedback,
                    reviewed_by = :tutor_id,
                    reviewed_at = NOW()
                WHERE id = :submission_id
            """),
            parameters,
        )

        updated = connection.execute(
            text(_SELECT_SUBMISSIONS + " AND ls.id = :submission_id"),
            parameters,
        ).mappings().one()

        return dict(updated)
