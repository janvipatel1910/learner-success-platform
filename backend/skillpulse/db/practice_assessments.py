"""Practice quizzes and timed mock exams for active cohort learners.

A practice assessment is any published assessment of the cohort's course
that is not used as a module check. Attempts are stored in the shared
``assessment_attempts`` and ``question_responses`` tables, so every answer
feeds readiness and analytics.
"""

import json
from datetime import timedelta
from uuid import UUID

from sqlalchemy import text

from skillpulse.core.assessment_grading import (
    InvalidAssessment,
    grade_assessment,
)
from skillpulse.db.connection import get_engine
from skillpulse.db.module_progress import _SCOPE_SQL

# Allow for network delay when a timed attempt is submitted at the deadline.
SUBMISSION_GRACE = timedelta(seconds=60)


class PracticeAccessDenied(Exception):
    """The user is not an active learner in this cohort."""


class PracticeNotFound(Exception):
    """The assessment or attempt does not exist in this scope."""


class PracticeConflict(Exception):
    """The request cannot be completed in the attempt's current state."""


_ASSESSMENTS = """
    SELECT a.*
    FROM assessments AS a
    JOIN courses AS c ON c.id = a.course_id
    WHERE a.course_id = :course_id
      AND c.organization_id = :organization_id
      AND a.status = 'published'
      AND NOT EXISTS (
          SELECT 1 FROM module_assessments AS ma
          WHERE ma.assessment_id = a.id
      )
"""

_QUESTIONS = text("""
    SELECT q.id, q.topic_id, q.question_text, q.question_type,
           q.options_json, q.correct_answer_json, q.explanation,
           q.status, aq.marks, aq.sequence_number,
           t.title AS topic_title
    FROM assessment_questions AS aq
    JOIN questions AS q ON q.id = aq.question_id
    JOIN topics AS t ON t.id = q.topic_id
    WHERE aq.assessment_id = :assessment_id
    ORDER BY aq.sequence_number
""")


def _require_learner(connection, parameters):
    if connection.execute(
        text(_SCOPE_SQL), parameters
    ).scalar_one_or_none() is None:
        raise PracticeAccessDenied()


def _assessment(connection, parameters, *, lock=False):
    row = connection.execute(
        text(
            _ASSESSMENTS
            + " AND a.id = :assessment_id"
            + (" FOR SHARE OF a" if lock else "")
        ),
        parameters,
    ).mappings().one_or_none()
    if row is None:
        raise PracticeNotFound()
    return row


def _questions(connection, assessment):
    questions = connection.execute(
        _QUESTIONS, {"assessment_id": assessment["id"]}
    ).mappings().all()
    if (
        len(questions) != assessment["question_count"]
        or any(q["status"] != "published" for q in questions)
    ):
        raise InvalidAssessment("Invalid practice question configuration.")
    return questions


def _deadline(assessment, started_at):
    if assessment["time_limit_minutes"] is None:
        return None
    return started_at + timedelta(minutes=assessment["time_limit_minutes"])


def _expire_overdue(connection, parameters):
    """Close timed attempts whose deadline (plus grace) has passed."""
    connection.execute(
        text("""
            UPDATE assessment_attempts AS aa
            SET status = 'expired', updated_at = NOW()
            FROM assessments AS a
            WHERE a.id = aa.assessment_id
              AND aa.learner_id = :learner_id
              AND aa.status = 'in_progress'
              AND a.time_limit_minutes IS NOT NULL
              AND NOW() > aa.started_at
                  + make_interval(mins => a.time_limit_minutes)
                  + make_interval(secs => :grace_seconds)
        """),
        {**parameters, "grace_seconds": SUBMISSION_GRACE.total_seconds()},
    )


def _parameters(organization_id, course_id, cohort_id, learner_id, **extra):
    return {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": learner_id,
        **extra,
    }


def list_practice_assessments(organization_id, course_id, cohort_id, learner_id):
    parameters = _parameters(organization_id, course_id, cohort_id, learner_id)

    with get_engine().begin() as connection:
        _require_learner(connection, parameters)
        _expire_overdue(connection, parameters)

        rows = connection.execute(
            text(f"""
                WITH practice AS ({_ASSESSMENTS})
                SELECT
                    p.id, p.title, p.assessment_type, p.question_count,
                    p.time_limit_minutes, p.pass_percentage,
                    p.maximum_attempts,
                    COUNT(aa.id) AS attempts_used,
                    MAX(aa.percentage) FILTER (
                        WHERE aa.status = 'submitted'
                    ) AS best_percentage,
                    (ARRAY_AGG(aa.id) FILTER (
                        WHERE aa.status = 'in_progress'
                    ))[1] AS in_progress_attempt_id
                FROM practice AS p
                LEFT JOIN assessment_attempts AS aa
                  ON aa.assessment_id = p.id
                 AND aa.learner_id = :learner_id
                GROUP BY p.id, p.title, p.assessment_type, p.question_count,
                         p.time_limit_minutes, p.pass_percentage,
                         p.maximum_attempts
                ORDER BY p.assessment_type, p.title
            """),
            parameters,
        ).mappings().all()

    return [
        {
            **dict(row),
            "attempts_remaining": max(
                0, row["maximum_attempts"] - row["attempts_used"]
            ),
        }
        for row in rows
    ]


def _attempt_payload(assessment, attempt, questions):
    return {
        "attempt_id": attempt["id"],
        "assessment_id": assessment["id"],
        "title": assessment["title"],
        "assessment_type": assessment["assessment_type"],
        "pass_percentage": assessment["pass_percentage"],
        "started_at": attempt["started_at"],
        "deadline": _deadline(assessment, attempt["started_at"]),
        # Never return answer keys or explanations before submission.
        "questions": [
            {
                "id": q["id"],
                "topic_title": q["topic_title"],
                "question_text": q["question_text"],
                "question_type": q["question_type"],
                "select_count": len(q["correct_answer_json"]),
                "options": q["options_json"],
            }
            for q in questions
        ],
    }


def start_attempt(organization_id, course_id, cohort_id, learner_id, assessment_id):
    """Start a new attempt, or resume the learner's open attempt."""
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id,
        assessment_id=assessment_id,
    )

    with get_engine().begin() as connection:
        _require_learner(connection, parameters)
        # Serialize attempt numbering for this learner.
        connection.execute(
            text("SELECT id FROM users WHERE id = :learner_id FOR UPDATE"),
            parameters,
        ).scalar_one()
        _expire_overdue(connection, parameters)

        assessment = _assessment(connection, parameters, lock=True)
        questions = _questions(connection, assessment)

        open_attempt = connection.execute(
            text("""
                SELECT id, started_at
                FROM assessment_attempts
                WHERE assessment_id = :assessment_id
                  AND learner_id = :learner_id
                  AND status = 'in_progress'
                ORDER BY started_at DESC
                LIMIT 1
            """),
            parameters,
        ).mappings().one_or_none()
        if open_attempt is not None:
            return _attempt_payload(assessment, open_attempt, questions)

        counts = connection.execute(
            text("""
                SELECT COUNT(*) AS used,
                       COALESCE(MAX(attempt_number), 0) + 1 AS next_number
                FROM assessment_attempts
                WHERE assessment_id = :assessment_id
                  AND learner_id = :learner_id
            """),
            parameters,
        ).mappings().one()
        if counts["used"] >= assessment["maximum_attempts"]:
            raise PracticeConflict("No attempts remain. Contact your tutor.")

        attempt = connection.execute(
            text("""
                INSERT INTO assessment_attempts (
                    assessment_id, learner_id, attempt_number, status
                )
                VALUES (
                    :assessment_id, :learner_id, :attempt_number, 'in_progress'
                )
                RETURNING id, started_at
            """),
            {**parameters, "attempt_number": counts["next_number"]},
        ).mappings().one()

        return _attempt_payload(assessment, attempt, questions)


def _review(connection, assessment, attempt):
    questions = _questions(connection, assessment)
    responses = {
        row["question_id"]: row
        for row in connection.execute(
            text("""
                SELECT question_id, selected_answer_json, is_correct
                FROM question_responses
                WHERE attempt_id = :attempt_id
            """),
            {"attempt_id": attempt["id"]},
        ).mappings()
    }

    topics: dict[str, dict[str, object]] = {}
    review = []
    for q in questions:
        response = responses.get(q["id"])
        is_correct = bool(response and response["is_correct"])
        topic = topics.setdefault(
            q["topic_title"],
            {"topic_title": q["topic_title"], "correct": 0, "total": 0},
        )
        topic["total"] += 1
        topic["correct"] += int(is_correct)
        review.append({
            "id": q["id"],
            "topic_title": q["topic_title"],
            "question_text": q["question_text"],
            "question_type": q["question_type"],
            "options": q["options_json"],
            "selected": (response or {}).get("selected_answer_json") or [],
            "correct_answer": q["correct_answer_json"],
            "is_correct": is_correct,
            "explanation": q["explanation"],
        })

    return {
        "attempt_id": attempt["id"],
        "assessment_id": assessment["id"],
        "title": assessment["title"],
        "score": attempt["score"],
        "percentage": attempt["percentage"],
        "passed": attempt["passed"],
        "submitted_at": attempt["submitted_at"],
        "topics": list(topics.values()),
        "questions": review,
    }


def _scoped_attempt(connection, parameters, *, lock=False):
    attempt = connection.execute(
        text(
            """
            SELECT *
            FROM assessment_attempts
            WHERE id = :attempt_id
              AND assessment_id = :assessment_id
              AND learner_id = :learner_id
            """
            + (" FOR UPDATE" if lock else "")
        ),
        parameters,
    ).mappings().one_or_none()
    if attempt is None:
        raise PracticeNotFound()
    return attempt


def submit_attempt(
    organization_id, course_id, cohort_id, learner_id,
    assessment_id, attempt_id, answers,
):
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id,
        assessment_id=assessment_id, attempt_id=attempt_id,
    )

    with get_engine().begin() as connection:
        _require_learner(connection, parameters)
        assessment = _assessment(connection, parameters, lock=True)
        attempt = _scoped_attempt(connection, parameters, lock=True)

        # Retrying the same request returns the original result.
        if attempt["status"] == "submitted":
            return _review(connection, assessment, attempt)
        if attempt["status"] != "in_progress":
            raise PracticeConflict("This attempt has expired.")

        deadline = _deadline(assessment, attempt["started_at"])
        now = connection.execute(text("SELECT NOW()")).scalar_one()
        if deadline is not None and now > deadline + SUBMISSION_GRACE:
            connection.execute(
                text("""
                    UPDATE assessment_attempts
                    SET status = 'expired', updated_at = NOW()
                    WHERE id = :attempt_id
                """),
                parameters,
            )
            raise PracticeConflict("Time is up. This attempt has expired.")

        questions = _questions(connection, assessment)
        result = grade_assessment(
            questions, answers, assessment["pass_percentage"]
        )

        for response in result["responses"]:
            connection.execute(
                text("""
                    INSERT INTO question_responses (
                        attempt_id, question_id, selected_answer_json,
                        is_correct, marks_awarded
                    )
                    VALUES (
                        :attempt_id, :question_id,
                        CAST(:selected_answer_json AS jsonb),
                        :is_correct, :marks_awarded
                    )
                """),
                {
                    **response,
                    "attempt_id": attempt_id,
                    "question_id": UUID(response["question_id"]),
                    "selected_answer_json": (
                        None
                        if response["selected_answer_json"] is None
                        else json.dumps(response["selected_answer_json"])
                    ),
                },
            )

        submitted = connection.execute(
            text("""
                UPDATE assessment_attempts
                SET status = 'submitted', submitted_at = NOW(),
                    score = :score, percentage = :percentage,
                    passed = :passed, updated_at = NOW()
                WHERE id = :attempt_id
                RETURNING *
            """),
            {
                **parameters,
                "score": result["score"],
                "percentage": result["percentage"],
                "passed": result["passed"],
            },
        ).mappings().one()

        return _review(connection, assessment, submitted)


def get_attempt_review(
    organization_id, course_id, cohort_id, learner_id,
    assessment_id, attempt_id,
):
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id,
        assessment_id=assessment_id, attempt_id=attempt_id,
    )
    with get_engine().begin() as connection:
        _require_learner(connection, parameters)
        assessment = _assessment(connection, parameters)
        attempt = _scoped_attempt(connection, parameters)
        if attempt["status"] != "submitted":
            raise PracticeConflict("Submit the attempt to see the review.")
        return _review(connection, assessment, attempt)
