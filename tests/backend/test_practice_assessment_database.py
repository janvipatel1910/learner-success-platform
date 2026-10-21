"""PostgreSQL integration tests for practice quizzes and timed exams."""

import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from skillpulse.db import practice_assessments as practice
from skillpulse.db.connection import get_engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_TESTS") != "true",
        reason="Set RUN_DATABASE_TESTS=true to run database checks.",
    ),
    pytest.mark.usefixtures("demo_course_content"),
]

CONTEXT = {
    "organization_id": UUID("10000000-0000-0000-0000-000000000001"),
    "course_id": UUID("40000000-0000-0000-0000-000000000001"),
    "cohort_id": UUID("42000000-0000-0000-0000-000000000001"),
    # Demo Learner Two has no seeded attempts on the practice content.
    "learner_id": UUID("20000000-0000-0000-0000-000000000004"),
}
VPC_QUIZ = UUID("63000000-0000-0000-0000-000000000001")
TIMED_EXAM = UUID("63000000-0000-0000-0000-000000000003")
MODULE_CHECK = UUID("61000000-0000-0000-0000-000000000011")


@pytest.fixture
def database(monkeypatch):
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            class TransactionEngine:
                @contextmanager
                def begin(self):
                    yield connection

            monkeypatch.setattr(practice, "get_engine", TransactionEngine)
            yield connection
        finally:
            transaction.rollback()


def answer_key(connection, assessment_id):
    rows = connection.execute(
        text("""
            SELECT q.id, q.correct_answer_json, q.options_json
            FROM assessment_questions AS aq
            JOIN questions AS q ON q.id = aq.question_id
            WHERE aq.assessment_id = :assessment_id
            ORDER BY aq.sequence_number
        """),
        {"assessment_id": assessment_id},
    ).mappings().all()
    return rows


def test_listing_shows_practice_but_not_module_checks(database):
    listing = practice.list_practice_assessments(**CONTEXT)
    ids = {row["id"] for row in listing}

    assert {VPC_QUIZ, TIMED_EXAM} <= ids
    assert MODULE_CHECK not in ids
    vpc = next(row for row in listing if row["id"] == VPC_QUIZ)
    assert vpc["attempts_used"] == 0
    assert vpc["attempts_remaining"] == 5


def test_start_hides_answers_and_resumes_open_attempt(database):
    first = practice.start_attempt(**CONTEXT, assessment_id=VPC_QUIZ)
    second = practice.start_attempt(**CONTEXT, assessment_id=VPC_QUIZ)

    assert first["attempt_id"] == second["attempt_id"]
    assert first["deadline"] is None
    assert len(first["questions"]) == 10
    for question in first["questions"]:
        assert "correct_answer_json" not in question
        assert "explanation" not in question
    assert any(q["select_count"] == 2 for q in first["questions"])


def test_submit_grades_records_responses_and_reviews(database):
    attempt = practice.start_attempt(**CONTEXT, assessment_id=VPC_QUIZ)
    key = answer_key(database, VPC_QUIZ)

    # Answer all but the last two correctly; leave one blank, one wrong.
    answers = {str(q["id"]): list(q["correct_answer_json"]) for q in key[:8]}
    wrong = next(o for o in key[8]["options_json"]
                 if o not in key[8]["correct_answer_json"])
    answers[str(key[8]["id"])] = [wrong]

    result = practice.submit_attempt(
        **CONTEXT,
        assessment_id=VPC_QUIZ,
        attempt_id=attempt["attempt_id"],
        answers=answers,
    )

    assert result["percentage"] == 80
    assert result["passed"] is True
    assert result["topics"] == [
        {"topic_title": "Networking and VPC", "correct": 8, "total": 10}
    ]
    assert result["questions"][9]["selected"] == []
    assert all(q["explanation"] for q in result["questions"])

    stored = database.execute(
        text("SELECT COUNT(*) FROM question_responses WHERE attempt_id = :id"),
        {"id": attempt["attempt_id"]},
    ).scalar_one()
    assert stored == 10

    # Retrying the submit returns the same result without new rows.
    again = practice.submit_attempt(
        **CONTEXT,
        assessment_id=VPC_QUIZ,
        attempt_id=attempt["attempt_id"],
        answers={},
    )
    assert again["percentage"] == result["percentage"]

    review = practice.get_attempt_review(
        **CONTEXT, assessment_id=VPC_QUIZ, attempt_id=attempt["attempt_id"]
    )
    assert review["score"] == result["score"]

    listing = practice.list_practice_assessments(**CONTEXT)
    vpc = next(row for row in listing if row["id"] == VPC_QUIZ)
    assert vpc["best_percentage"] == 80
    assert vpc["attempts_remaining"] == 4


def test_timed_exam_has_deadline_and_expires(database):
    attempt = practice.start_attempt(**CONTEXT, assessment_id=TIMED_EXAM)
    assert attempt["deadline"] is not None
    assert len(attempt["questions"]) == 20

    database.execute(
        text("""
            UPDATE assessment_attempts
            SET started_at = NOW() - INTERVAL '2 hours'
            WHERE id = :id
        """),
        {"id": attempt["attempt_id"]},
    )

    with pytest.raises(practice.PracticeConflict, match="Time is up"):
        practice.submit_attempt(
            **CONTEXT,
            assessment_id=TIMED_EXAM,
            attempt_id=attempt["attempt_id"],
            answers={},
        )

    status = database.execute(
        text("SELECT status FROM assessment_attempts WHERE id = :id"),
        {"id": attempt["attempt_id"]},
    ).scalar_one()
    assert status == "expired"


def test_attempt_limit_is_enforced(database):
    for _ in range(5):
        attempt = practice.start_attempt(**CONTEXT, assessment_id=VPC_QUIZ)
        practice.submit_attempt(
            **CONTEXT,
            assessment_id=VPC_QUIZ,
            attempt_id=attempt["attempt_id"],
            answers={},
        )

    with pytest.raises(practice.PracticeConflict, match="No attempts remain"):
        practice.start_attempt(**CONTEXT, assessment_id=VPC_QUIZ)


def test_scope_is_enforced(database):
    with pytest.raises(practice.PracticeAccessDenied):
        practice.list_practice_assessments(
            **{**CONTEXT, "learner_id": UUID("20000000-0000-0000-0000-000000000002")}
        )

    with pytest.raises(practice.PracticeNotFound):
        practice.start_attempt(**CONTEXT, assessment_id=MODULE_CHECK)

    with pytest.raises(practice.PracticeNotFound):
        practice.get_attempt_review(
            **CONTEXT, assessment_id=VPC_QUIZ, attempt_id=uuid4()
        )
