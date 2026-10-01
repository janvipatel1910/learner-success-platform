"""Module checks, server-side grading and atomic completion."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import text

from skillpulse.core.module_assessment import (
    InvalidAssessment,
    grade_module_check,
)
from skillpulse.db.connection import get_engine
from skillpulse.db.module_progress import (
    ModuleAccessDenied,
    ModuleLocked,
    ModuleNotFound,
    _LIST_MODULES,
    _SCOPE_SQL,
)


class CheckUnavailable(Exception):
    """No published module check is available."""


class CheckConflict(Exception):
    """The check cannot be submitted in its current state."""


def _parameters(organization_id, course_id, cohort_id, learner_id, topic_id):
    return {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": learner_id,
        "topic_id": topic_id,
    }


def _module(connection, parameters, *, lock=False):
    scope = _SCOPE_SQL + (" FOR UPDATE OF cm" if lock else "")
    membership = connection.execute(
        text(scope), parameters
    ).scalar_one_or_none()

    if membership is None:
        raise ModuleAccessDenied()

    modules = connection.execute(
        _LIST_MODULES, parameters
    ).mappings().all()
    module = next(
        (
            row for row in modules
            if row["topic_id"] == parameters["topic_id"]
        ),
        None,
    )
    if module is None:
        raise ModuleNotFound()
    if module["status"] == "locked":
        raise ModuleLocked()
    return module


def _configuration(connection, parameters):
    assessment = connection.execute(
        text("""
            SELECT a.*
            FROM module_assessments AS ma
            JOIN assessments AS a
              ON a.id = ma.assessment_id
             AND a.course_id = ma.course_id
            WHERE ma.topic_id = :topic_id
              AND ma.course_id = :course_id
              AND a.status = 'published'
            FOR SHARE OF ma, a
        """),
        parameters,
    ).mappings().one_or_none()

    if assessment is None:
        raise CheckUnavailable()

    # Timed checks need a separate persisted start/deadline workflow.
    if assessment["time_limit_minutes"] is not None:
        raise CheckConflict("Timed module checks are not supported yet.")

    questions = connection.execute(
        text("""
            SELECT q.*, aq.marks, aq.sequence_number
            FROM assessment_questions AS aq
            JOIN questions AS q ON q.id = aq.question_id
            WHERE aq.assessment_id = :assessment_id
            ORDER BY aq.sequence_number
            FOR SHARE OF aq, q
        """),
        {"assessment_id": assessment["id"]},
    ).mappings().all()

    if (
        len(questions) != assessment["question_count"]
        or any(
            q["topic_id"] != parameters["topic_id"]
            or q["status"] != "published"
            for q in questions
        )
    ):
        raise InvalidAssessment("Invalid module question configuration.")

    # Validate server-owned configuration before showing the check.
    grade_module_check(
        questions,
        {str(q["id"]): q["correct_answer_json"] for q in questions},
        assessment["pass_percentage"],
    )

    # Detect edits between loading the check and submitting answers.
    version_data = {
        "assessment_id": assessment["id"],
        "updated_at": assessment["updated_at"],
        "pass_percentage": assessment["pass_percentage"],
        "maximum_attempts": assessment["maximum_attempts"],
        "questions": [
            {
                "id": q["id"],
                "updated_at": q["updated_at"],
                "marks": q["marks"],
                "sequence_number": q["sequence_number"],
            }
            for q in questions
        ],
    }
    version = hashlib.sha256(
        json.dumps(version_data, sort_keys=True, default=str).encode()
    ).hexdigest()
    return assessment, questions, version


def get_module_check(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    topic_id: UUID,
):
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id, topic_id
    )
    with get_engine().begin() as connection:
        module = _module(connection, parameters)
        if module["status"] == "available":
            raise CheckConflict("Start the module before opening its check.")

        assessment, questions, version = _configuration(
            connection, parameters
        )
        used = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM assessment_attempts
                WHERE assessment_id = :assessment_id
                  AND learner_id = :learner_id
            """),
            {**parameters, "assessment_id": assessment["id"]},
        ).scalar_one()

        return {
            "assessment_id": assessment["id"],
            "title": assessment["title"],
            "version": version,
            "pass_percentage": assessment["pass_percentage"],
            "maximum_attempts": assessment["maximum_attempts"],
            "attempts_remaining": max(
                0, assessment["maximum_attempts"] - used
            ),
            "module_status": module["status"],
            # Never return answer keys or explanations before submission.
            "questions": [
                {
                    "id": q["id"],
                    "question_text": q["question_text"],
                    "options": q["options_json"],
                }
                for q in questions
            ],
        }


def submit_module_check(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    topic_id: UUID,
    attempt_id: UUID,
    version: str,
    answers: dict[str, list[str]],
):
    parameters = _parameters(
        organization_id, course_id, cohort_id, learner_id, topic_id
    )
    parameters["attempt_id"] = attempt_id

    with get_engine().begin() as connection:
        module = _module(connection, parameters, lock=True)

        # Serialize attempt numbering across this learner's cohorts.
        connection.execute(
            text("SELECT id FROM users WHERE id = :learner_id FOR UPDATE"),
            parameters,
        ).scalar_one()

        # Retrying the same request returns its original result.
        existing = connection.execute(
            text("""
                SELECT aa.id AS attempt_id, aa.score,
                       aa.percentage, aa.passed
                FROM module_assessment_attempts AS ma
                JOIN assessment_attempts AS aa ON aa.id = ma.attempt_id
                JOIN module_progress AS mp ON mp.id = ma.module_progress_id
                WHERE aa.id = :attempt_id
                  AND aa.learner_id = :learner_id
                  AND mp.learner_id = :learner_id
                  AND mp.cohort_id = :cohort_id
                  AND mp.topic_id = :topic_id
                  AND aa.status = 'submitted'
            """),
            parameters,
        ).mappings().one_or_none()

        if existing is not None:
            return {
                **dict(existing),
                "module_status": module["status"],
            }

        if module["status"] != "in_progress":
            raise CheckConflict(
                "The module must be in progress to submit a new attempt."
            )

        if connection.execute(
            text("SELECT 1 FROM assessment_attempts WHERE id = :attempt_id"),
            parameters,
        ).scalar_one_or_none() is not None:
            raise CheckConflict("Attempt identifier is already in use.")

        assessment, questions, current_version = _configuration(
            connection, parameters
        )
        if version != current_version:
            raise CheckConflict("The check changed. Reload it before submitting.")

        parameters["assessment_id"] = assessment["id"]
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
            raise CheckConflict("No attempts remain. Contact your tutor.")

        result = grade_module_check(
            questions, answers, assessment["pass_percentage"]
        )
        parameters.update({
            "attempt_number": counts["next_number"],
            "score": result["score"],
            "percentage": result["percentage"],
            "passed": result["passed"],
        })

        connection.execute(
            text("""
                INSERT INTO assessment_attempts (
                    id, assessment_id, learner_id, attempt_number,
                    started_at, submitted_at, score, percentage,
                    passed, status
                )
                VALUES (
                    :attempt_id, :assessment_id, :learner_id, :attempt_number,
                    NOW(), NOW(), :score, :percentage,
                    :passed, 'submitted'
                )
            """),
            parameters,
        )

        connection.execute(
            text("""
                INSERT INTO module_assessment_attempts (
                    attempt_id, module_progress_id, learner_id
                )
                SELECT :attempt_id, id, learner_id
                FROM module_progress
                WHERE cohort_id = :cohort_id
                  AND learner_id = :learner_id
                  AND topic_id = :topic_id
            """),
            parameters,
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
                    "selected_answer_json": json.dumps(
                        response["selected_answer_json"]
                    ),
                },
            )

        if result["passed"]:
            connection.execute(
                text("""
                    UPDATE module_progress
                    SET status = 'completed', completed_at = NOW()
                    WHERE cohort_id = :cohort_id
                      AND learner_id = :learner_id
                      AND topic_id = :topic_id
                      AND status = 'in_progress'
                """),
                parameters,
            )

        return {
            "attempt_id": attempt_id,
            "score": result["score"],
            "percentage": result["percentage"],
            "passed": result["passed"],
            "module_status": (
                "completed" if result["passed"] else "in_progress"
            ),
        }
