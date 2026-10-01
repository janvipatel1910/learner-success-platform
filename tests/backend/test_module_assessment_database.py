"""Database tests for module checks and completion."""

import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from skillpulse.core.module_assessment import InvalidAnswers
from skillpulse.db import module_assessments as checks
from skillpulse.db import module_progress as progress
from skillpulse.db.connection import get_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run database checks.",
)

CONTEXT = {
    "organization_id": UUID("10000000-0000-0000-0000-000000000001"),
    "course_id": UUID("40000000-0000-0000-0000-000000000001"),
    "cohort_id": UUID("42000000-0000-0000-0000-000000000001"),
    "learner_id": UUID("20000000-0000-0000-0000-000000000003"),
}
VPC = UUID("41000000-0000-0000-0000-000000000001")
S3 = UUID("41000000-0000-0000-0000-000000000002")

ATTEMPTS = """
    SELECT aa.id
    FROM assessment_attempts AS aa
    JOIN module_assessments AS ma
      ON ma.assessment_id = aa.assessment_id
    WHERE aa.learner_id = :learner_id
      AND ma.course_id = :course_id
"""


@pytest.fixture
def database(monkeypatch):
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            # Temporarily isolate demo module attempts.
            for table in ("question_responses", "module_assessment_attempts"):
                connection.execute(
                    text(
                        f"DELETE FROM {table} "
                        f"WHERE attempt_id IN ({ATTEMPTS})"
                    ),
                    CONTEXT,
                )

            connection.execute(
                text(
                    f"DELETE FROM assessment_attempts "
                    f"WHERE id IN ({ATTEMPTS})"
                ),
                CONTEXT,
            )
            connection.execute(
                text("""
                    UPDATE module_progress
                    SET status = 'in_progress', completed_at = NULL
                    WHERE cohort_id = :cohort_id
                      AND learner_id = :learner_id
                """),
                CONTEXT,
            )

            class TransactionEngine:
                @contextmanager
                def begin(self):
                    yield connection

            engine = TransactionEngine()
            monkeypatch.setattr(checks, "get_engine", lambda: engine)
            monkeypatch.setattr(progress, "get_engine", lambda: engine)

            progress.start_learner_module(**CONTEXT, topic_id=VPC)
            check = checks.get_module_check(**CONTEXT, topic_id=VPC)

            question = connection.execute(
                text("""
                    SELECT q.*
                    FROM questions AS q
                    JOIN assessment_questions AS aq
                      ON aq.question_id = q.id
                    WHERE aq.assessment_id = :assessment_id
                """),
                {"assessment_id": check["assessment_id"]},
            ).mappings().one()

            correct = {
                str(question["id"]): list(question["correct_answer_json"])
            }
            wrong_option = next(
                option for option in question["options_json"]
                if option not in question["correct_answer_json"]
            )
            wrong = {str(question["id"]): [wrong_option]}

            yield connection, check, correct, wrong
        finally:
            transaction.rollback()


def submit(check, answers, attempt_id=None):
    return checks.submit_module_check(
        **CONTEXT,
        topic_id=VPC,
        attempt_id=attempt_id or uuid4(),
        version=check["version"],
        answers=answers,
    )


def test_question_response_does_not_expose_answers(database):
    _, check, _, _ = database
    question = check["questions"][0]

    assert set(question) == {"id", "question_text", "options"}
    assert check["attempts_remaining"] == 3


def test_pass_completes_module_and_unlocks_next(database):
    connection, check, correct, _ = database
    result = submit(check, correct)

    assert result["passed"] is True
    assert result["module_status"] == "completed"

    modules = progress.list_learner_modules(**CONTEXT)
    assert modules[0]["status"] == "completed"
    assert modules[1]["status"] in {"available", "in_progress"}

    saved = connection.execute(
        text("""
            SELECT is_correct, marks_awarded
            FROM question_responses
            WHERE attempt_id = :attempt_id
        """),
        {"attempt_id": result["attempt_id"]},
    ).mappings().one()

    assert saved["is_correct"] is True
    assert saved["marks_awarded"] > 0


def test_failure_keeps_next_module_locked(database):
    _, check, _, wrong = database
    result = submit(check, wrong)

    assert result["passed"] is False
    assert result["module_status"] == "in_progress"
    assert progress.list_learner_modules(
        **CONTEXT
    )[1]["status"] == "locked"


def test_duplicate_submission_reuses_original_result(database):
    connection, check, correct, _ = database
    attempt_id = uuid4()

    first = submit(check, correct, attempt_id)
    retry = submit(check, correct, attempt_id)

    assert retry == first
    count = connection.execute(
        text("""
            SELECT COUNT(*) FROM assessment_attempts
            WHERE assessment_id = :assessment_id
              AND learner_id = :learner_id
        """),
        {**CONTEXT, "assessment_id": check["assessment_id"]},
    ).scalar_one()
    assert count == 1


def test_three_failures_exhaust_attempts(database):
    _, check, _, wrong = database

    for _ in range(3):
        assert submit(check, wrong)["passed"] is False

    with pytest.raises(checks.CheckConflict, match="No attempts remain"):
        submit(check, wrong)

    refreshed = checks.get_module_check(**CONTEXT, topic_id=VPC)
    assert refreshed["attempts_remaining"] == 0


def test_invalid_answers_do_not_consume_attempt(database):
    _, check, _, _ = database

    with pytest.raises(InvalidAnswers):
        submit(check, {})

    refreshed = checks.get_module_check(**CONTEXT, topic_id=VPC)
    assert refreshed["attempts_remaining"] == 3


def test_stale_check_version_is_rejected(database):
    _, check, correct, _ = database

    with pytest.raises(checks.CheckConflict, match="check changed"):
        submit({**check, "version": "0" * 64}, correct)

    assert checks.get_module_check(
        **CONTEXT, topic_id=VPC
    )["attempts_remaining"] == 3


def test_locked_module_cannot_load_or_submit_check(database):
    with pytest.raises(progress.ModuleLocked):
        checks.get_module_check(**CONTEXT, topic_id=S3)

    with pytest.raises(progress.ModuleLocked):
        checks.submit_module_check(
            **CONTEXT,
            topic_id=S3,
            attempt_id=uuid4(),
            version="0" * 64,
            answers={},
        )
