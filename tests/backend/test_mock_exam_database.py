"""Database checks for the 65-question mock exam, readiness and the certificate."""

import os
from contextlib import contextmanager
from uuid import UUID

import pytest
from sqlalchemy import text

from skillpulse.db import certificate_eligibility, readiness
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
    # Demo Learner Two has no seeded mock exam attempts.
    "learner_id": UUID("20000000-0000-0000-0000-000000000004"),
}
MOCK_EXAM = UUID("63000000-0000-0000-0000-000000000004")


@pytest.fixture
def database(monkeypatch):
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:

            class TransactionEngine:
                @contextmanager
                def begin(self):
                    yield connection

                @contextmanager
                def connect(self):
                    yield connection

            for module in (practice, readiness, certificate_eligibility):
                monkeypatch.setattr(module, "get_engine", TransactionEngine)
            yield connection
        finally:
            transaction.rollback()


def answer_key(connection):
    return connection.execute(
        text("""
            SELECT q.id, q.correct_answer_json, q.options_json
            FROM assessment_questions AS aq
            JOIN questions AS q ON q.id = aq.question_id
            WHERE aq.assessment_id = :assessment_id
            ORDER BY aq.sequence_number
        """),
        {"assessment_id": MOCK_EXAM},
    ).mappings().all()


def sit_exam(connection, correct_count):
    """Answer the first `correct_count` questions correctly, the rest wrongly."""
    attempt = practice.start_attempt(**CONTEXT, assessment_id=MOCK_EXAM)
    answers = {}
    for number, question in enumerate(answer_key(connection)):
        if number < correct_count:
            answers[str(question["id"])] = list(question["correct_answer_json"])
        else:
            wrong = [
                option for option in question["options_json"]
                if option not in question["correct_answer_json"]
            ]
            answers[str(question["id"])] = wrong[: len(question["correct_answer_json"])]
    return practice.submit_attempt(
        **CONTEXT,
        assessment_id=MOCK_EXAM,
        attempt_id=attempt["attempt_id"],
        answers=answers,
    )


def test_mock_exam_is_listed_as_a_timed_mock_exam(database):
    listing = practice.list_practice_assessments(**CONTEXT)
    mock = next(row for row in listing if row["id"] == MOCK_EXAM)

    assert mock["assessment_type"] == "mock_exam"
    assert mock["question_count"] == 65
    assert mock["time_limit_minutes"] == 130
    assert float(mock["pass_percentage"]) == 70
    assert mock["attempts_remaining"] == 3


def test_start_gives_65_questions_and_a_130_minute_deadline(database):
    attempt = practice.start_attempt(**CONTEXT, assessment_id=MOCK_EXAM)

    assert len(attempt["questions"]) == 65
    assert (attempt["deadline"] - attempt["started_at"]).total_seconds() == 130 * 60
    assert sum(q["select_count"] == 2 for q in attempt["questions"]) == 6
    topics = {q["topic_title"] for q in attempt["questions"]}
    assert topics == {"Networking and VPC", "Storage and S3"}
    for question in attempt["questions"]:
        assert "correct_answer_json" not in question


def test_mock_exam_questions_are_new(database):
    """The mock exam must not reuse practice or module check questions."""
    shared = database.execute(
        text("""
            SELECT COUNT(*)
            FROM assessment_questions AS mock
            JOIN assessment_questions AS other
              ON other.question_id = mock.question_id
             AND other.assessment_id <> mock.assessment_id
            WHERE mock.assessment_id = :assessment_id
        """),
        {"assessment_id": MOCK_EXAM},
    ).scalar_one()

    assert shared == 0


def test_46_of_65_passes_and_counts_for_readiness_and_certificate(database):
    result = sit_exam(database, 46)

    assert round(float(result["percentage"]), 2) == 70.77
    assert result["passed"] is True

    inputs = readiness.get_readiness_inputs(**CONTEXT)
    assert round(float(inputs["mock_component"]), 2) == 70.77

    eligibility = certificate_eligibility.evaluate_certificate_eligibility(**CONTEXT)
    assert eligibility["mock_score_met"] is True


def test_45_of_65_fails_and_does_not_meet_the_certificate_rule(database):
    result = sit_exam(database, 45)

    assert round(float(result["percentage"]), 2) == 69.23
    assert result["passed"] is False

    eligibility = certificate_eligibility.evaluate_certificate_eligibility(**CONTEXT)
    assert eligibility["mock_score_met"] is False
