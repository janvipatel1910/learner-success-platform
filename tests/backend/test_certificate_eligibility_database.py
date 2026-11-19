"""Database checks for certificate eligibility rules."""

import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from skillpulse.db import certificate_eligibility as repository
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


@pytest.fixture
def database(monkeypatch):
    """Give the learner one completed class and no active blockers.

    Everything happens in a transaction that is rolled back afterwards.
    """
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            # Only the class created below should count for attendance.
            connection.execute(
                text("""
                    UPDATE class_sessions SET status = 'cancelled'
                    WHERE cohort_id = :cohort_id
                """),
                CONTEXT,
            )
            connection.execute(
                text("""
                    UPDATE blockers
                    SET status = 'resolved',
                        resolved_at = NOW(),
                        resolution_summary = 'Resolved for test.'
                    WHERE cohort_id = :cohort_id
                      AND learner_id = :learner_id
                      AND status IN ('open', 'assigned', 'waiting_student')
                """),
                CONTEXT,
            )
            session_id = uuid4()
            connection.execute(
                text("""
                    INSERT INTO class_sessions (
                        id, cohort_id, topic_id, title,
                        scheduled_start, scheduled_end, status
                    )
                    VALUES (
                        :session_id, :cohort_id, :topic_id,
                        'Certificate test class',
                        NOW() - INTERVAL '2 hours',
                        NOW() - INTERVAL '1 hour',
                        'completed'
                    )
                """),
                {**CONTEXT, "session_id": session_id, "topic_id": VPC},
            )

            class TransactionEngine:
                @contextmanager
                def begin(self):
                    yield connection

            monkeypatch.setattr(
                repository, "get_engine", lambda: TransactionEngine()
            )

            def set_attendance(status: str) -> None:
                connection.execute(
                    text("""
                        INSERT INTO attendance_records (
                            session_id, learner_id, attendance_status
                        )
                        VALUES (
                            :session_id, :learner_id,
                            CAST(:status AS attendance_status)
                        )
                        ON CONFLICT (session_id, learner_id)
                        DO UPDATE SET attendance_status = EXCLUDED.attendance_status
                    """),
                    {**CONTEXT, "session_id": session_id, "status": status},
                )

            yield connection, set_attendance
        finally:
            transaction.rollback()


def evaluate():
    return repository.evaluate_certificate_eligibility(**CONTEXT)


def test_attendance_is_met_when_learner_attended(database):
    _, set_attendance = database
    set_attendance("present")

    assert evaluate()["attendance_met"] is True


def test_late_counts_as_attended(database):
    _, set_attendance = database
    set_attendance("late")

    assert evaluate()["attendance_met"] is True


def test_attendance_is_not_met_when_learner_was_absent(database):
    _, set_attendance = database
    set_attendance("absent")

    result = evaluate()
    assert result["attendance_met"] is False
    assert "attendance_met" in result["missing_requirements_json"]


def test_open_blocker_stops_blockers_cleared(database):
    connection, _ = database
    assert evaluate()["blockers_cleared"] is True

    connection.execute(
        text("""
            INSERT INTO blockers (
                learner_id, cohort_id, topic_id, title, description,
                category, severity, status
            )
            VALUES (
                :learner_id, :cohort_id, :topic_id, 'Stuck on routing',
                'Test blocker.', 'concept', 'low', 'open'
            )
        """),
        {**CONTEXT, "topic_id": VPC},
    )

    assert evaluate()["blockers_cleared"] is False


def test_labs_and_mock_follow_readiness_minimums(database):
    connection, _ = database
    inputs = connection.execute(
        repository._GET_READINESS_INPUTS, CONTEXT
    ).mappings().one()

    result = evaluate()

    assert result["lab_met"] is (
        inputs["lab_component"] >= inputs["minimum_lab_completion"]
    )
    assert result["mock_score_met"] is (
        inputs["mock_component"] >= inputs["minimum_mock_score"]
    )


def test_not_eligible_while_assignments_are_not_built(database):
    _, set_attendance = database
    set_attendance("present")

    result = evaluate()

    assert result["assignment_met"] is False
    assert result["is_eligible"] is False
