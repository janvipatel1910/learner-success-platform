"""PostgreSQL integration tests for learner readiness inputs."""

import os
from uuid import UUID

import pytest

from scripts.seed_synthetic_data import load_synthetic_data
from skillpulse.db import readiness as repository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_TESTS") != "true",
        reason="Set RUN_DATABASE_TESTS=true",
    ),
    pytest.mark.skipif(
        os.getenv("RUN_SEED_TESTS") != "true",
        reason="Set RUN_SEED_TESTS=true",
    ),
]

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")
LEARNER_ID = UUID("20000000-0000-0000-0000-000000000003")
TUTOR_ID = UUID("20000000-0000-0000-0000-000000000002")
MODEL_ID = UUID("80000000-0000-0000-0000-000000000001")
UNKNOWN_ID = UUID("00000000-0000-0000-0000-000000000099")


@pytest.fixture(scope="module", autouse=True)
def seed_readiness_data() -> None:
    """Load the existing synthetic development fixtures."""
    load_synthetic_data()


def test_seeded_learner_has_readiness_inputs() -> None:
    result = repository.get_readiness_inputs(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        LEARNER_ID,
    )

    assert result is not None
    assert result["readiness_model_id"] == MODEL_ID

    weights = {
        name: float(value)
        for name, value in result["component_weights_json"].items()
    }
    assert weights == pytest.approx(
        {
            "quiz": 0.20,
            "mock": 0.30,
            "lab": 0.20,
            "attendance": 0.15,
            "blockers": 0.15,
        }
    )

    assert float(result["readiness_threshold"]) == 75
    assert float(result["minimum_mock_score"]) == 70
    assert float(result["minimum_lab_completion"]) == 80

    for column in (
        "quiz_component",
        "mock_component",
        "lab_component",
        "attendance_component",
        "blocker_component",
    ):
        assert 0 <= float(result[column]) <= 100, column


@pytest.mark.parametrize(
    ("organization_id", "course_id", "cohort_id", "learner_id"),
    [
        (
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            LEARNER_ID,
        ),
        (
            ORGANIZATION_ID,
            UNKNOWN_ID,
            COHORT_ID,
            LEARNER_ID,
        ),
        (
            ORGANIZATION_ID,
            COURSE_ID,
            UNKNOWN_ID,
            LEARNER_ID,
        ),
        (
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            UNKNOWN_ID,
        ),
        (
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            TUTOR_ID,
        ),
    ],
    ids=[
        "other-organization",
        "unknown-course",
        "unknown-cohort",
        "unknown-learner",
        "tutor-is-not-learner",
    ],
)
def test_invalid_scope_returns_no_inputs(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
) -> None:
    result = repository.get_readiness_inputs(
        organization_id,
        course_id,
        cohort_id,
        learner_id,
    )

    assert result is None
def test_attendance_counts_only_eligible_sessions(monkeypatch) -> None:
    from contextlib import contextmanager
    from datetime import timedelta
    from types import SimpleNamespace
    from uuid import uuid4

    from sqlalchemy import text
    from skillpulse.db.connection import get_engine

    temporary_cohort_id = uuid4()
    topic_id = UUID("41000000-0000-0000-0000-000000000001")

    with get_engine().connect() as connection:
        transaction = connection.begin()

        try:
            now = connection.execute(
                text("SELECT CURRENT_TIMESTAMP")
            ).scalar_one()
            enrolled_at = now - timedelta(days=10)

            connection.execute(
                text("""
                    INSERT INTO cohorts (
                        id, course_id, name, start_date,
                        end_date, delivery_mode, status
                    )
                    SELECT
                        :id, course_id, :name, :start_date,
                        NULL, delivery_mode, status
                    FROM cohorts
                    WHERE id = :source_id
                """),
                {
                    "id": temporary_cohort_id,
                    "name": f"Readiness attendance test {temporary_cohort_id}",
                    "start_date": enrolled_at.date(),
                    "source_id": COHORT_ID,
                },
            )

            connection.execute(
                text("""
                    INSERT INTO cohort_memberships (
                        cohort_id, user_id, cohort_role,
                        status, enrolled_at
                    )
                    VALUES (
                        :cohort_id, :learner_id, 'learner',
                        'active', :enrolled_at
                    )
                """),
                {
                    "cohort_id": temporary_cohort_id,
                    "learner_id": LEARNER_ID,
                    "enrolled_at": enrolled_at,
                },
            )

            # days relative to now, session status, attendance status
            cases = [
                (-9, "completed", "present"),
                (-8, "completed", "late"),
                (-7, "completed", "absent"),
                (-6, "completed", None),       # Missing: counts as zero
                (-5, "completed", "excused"),  # Excluded
                (-4, "scheduled", "present"),  # Excluded
                (-3, "cancelled", "present"),  # Excluded
                (-11, "completed", "present"), # Before enrolment
                (1, "completed", "present"),   # Future: excluded
            ]

            for days, session_status, attendance_status in cases:
                session_id = uuid4()
                start = now + timedelta(days=days)

                connection.execute(
                    text("""
                        INSERT INTO class_sessions (
                            id, cohort_id, topic_id, title,
                            scheduled_start, scheduled_end, status
                        )
                        VALUES (
                            :id, :cohort_id, :topic_id, :title,
                            :start, :end, :status
                        )
                    """),
                    {
                        "id": session_id,
                        "cohort_id": temporary_cohort_id,
                        "topic_id": topic_id,
                        "title": f"Attendance test {days}",
                        "start": start,
                        "end": start + timedelta(hours=1),
                        "status": session_status,
                    },
                )

                if attendance_status is not None:
                    connection.execute(
                        text("""
                            INSERT INTO attendance_records (
                                session_id, learner_id, attendance_status
                            )
                            VALUES (:session_id, :learner_id, :status)
                        """),
                        {
                            "session_id": session_id,
                            "learner_id": LEARNER_ID,
                            "status": attendance_status,
                        },
                    )

            @contextmanager
            def use_test_connection():
                yield connection

            # Run the real repository query inside this test transaction.
            monkeypatch.setattr(
                repository,
                "get_engine",
                lambda: SimpleNamespace(connect=use_test_connection),
            )

            result = repository.get_readiness_inputs(
                ORGANIZATION_ID,
                COURSE_ID,
                temporary_cohort_id,
                LEARNER_ID,
            )

            assert result is not None
            assert float(result["attendance_component"]) == pytest.approx(50.0)

        finally:
            transaction.rollback()
def test_snapshot_is_saved_and_invalid_scope_is_rejected(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from sqlalchemy import text
    from skillpulse.db.connection import get_engine

    with get_engine().connect() as connection:
        transaction = connection.begin()

        try:
            @contextmanager
            def use_test_transaction():
                yield connection

            monkeypatch.setattr(
                repository,
                "get_engine",
                lambda: SimpleNamespace(begin=use_test_transaction),
            )

            snapshot = repository.create_readiness_snapshot(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                LEARNER_ID,
            )

            assert snapshot is not None
            assert snapshot["learner_id"] == LEARNER_ID
            assert snapshot["cohort_id"] == COHORT_ID
            assert snapshot["readiness_model_id"] == MODEL_ID
            assert snapshot["calculated_at"] is not None

            saved = connection.execute(
                text("""
                    SELECT *
                    FROM readiness_snapshots
                    WHERE id = :id
                """),
                {"id": snapshot["id"]},
            ).mappings().one()

            explanation = saved["explanation_json"]
            components = explanation["components"]
            weights = explanation["weights"]

            expected_score = round(
                sum(
                    components[name] * weights[name]
                    for name in components
                ),
                2,
            )
            assert float(saved["overall_score"]) == pytest.approx(
                expected_score
            )
            assert explanation["thresholds"] == {
                "readiness_threshold": 75.0,
                "minimum_mock_score": 70.0,
                "minimum_lab_completion": 80.0,
            }

            for name, column in {
                "quiz": "quiz_component",
                "mock": "mock_component",
                "lab": "lab_component",
                "attendance": "attendance_component",
                "blockers": "blocker_component",
            }.items():
                assert float(saved[column]) == pytest.approx(
                    components[name], abs=0.0051
                )

            count_before = connection.execute(
                text("SELECT COUNT(*) FROM readiness_snapshots")
            ).scalar_one()

            rejected = repository.create_readiness_snapshot(
                OTHER_ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                LEARNER_ID,
            )

            assert rejected is None

            count_after = connection.execute(
                text("SELECT COUNT(*) FROM readiness_snapshots")
            ).scalar_one()

            assert count_after == count_before

        finally:
            transaction.rollback()
def test_snapshot_history_order_pagination_and_scope(monkeypatch):
    from contextlib import contextmanager
    from datetime import timedelta
    from types import SimpleNamespace
    from uuid import uuid4

    from sqlalchemy import text
    from skillpulse.db.connection import get_engine

    temporary_cohort_id = uuid4()

    with get_engine().connect() as connection:
        transaction = connection.begin()

        try:
            connection.execute(
                text("""
                    INSERT INTO cohorts (
                        id, course_id, name, start_date,
                        end_date, delivery_mode, status
                    )
                    SELECT
                        :id, course_id, :name, start_date,
                        end_date, delivery_mode, status
                    FROM cohorts
                    WHERE id = :source_id
                """),
                {
                    "id": temporary_cohort_id,
                    "name": f"History test {temporary_cohort_id}",
                    "source_id": COHORT_ID,
                },
            )
            connection.execute(
                text("""
                    INSERT INTO cohort_memberships (
                        cohort_id, user_id, cohort_role,
                        status, enrolled_at
                    )
                    VALUES (
                        :cohort_id, :learner_id, 'learner',
                        'active', CURRENT_TIMESTAMP
                    )
                """),
                {
                    "cohort_id": temporary_cohort_id,
                    "learner_id": LEARNER_ID,
                },
            )

            @contextmanager
            def use_test_connection():
                yield connection

            monkeypatch.setattr(
                repository,
                "get_engine",
                lambda: SimpleNamespace(
                    connect=use_test_connection,
                    begin=use_test_connection,
                ),
            )

            now = connection.execute(
                text("SELECT CURRENT_TIMESTAMP")
            ).scalar_one()

            snapshot_ids = []

            for days_ago in (3, 2, 1):
                snapshot = repository.create_readiness_snapshot(
                    ORGANIZATION_ID,
                    COURSE_ID,
                    temporary_cohort_id,
                    LEARNER_ID,
                )
                assert snapshot is not None
                snapshot_ids.append(snapshot["id"])

                connection.execute(
                    text("""
                        UPDATE readiness_snapshots
                        SET calculated_at = :calculated_at
                        WHERE id = :id
                    """),
                    {
                        "id": snapshot["id"],
                        "calculated_at": now - timedelta(days=days_ago),
                    },
                )

            history = repository.list_readiness_snapshots(
                ORGANIZATION_ID,
                COURSE_ID,
                temporary_cohort_id,
                LEARNER_ID,
            )
            assert [row["id"] for row in history] == snapshot_ids[::-1]

            page = repository.list_readiness_snapshots(
                ORGANIZATION_ID,
                COURSE_ID,
                temporary_cohort_id,
                LEARNER_ID,
                limit=1,
                offset=1,
            )
            assert [row["id"] for row in page] == [snapshot_ids[1]]

            beyond_end = repository.list_readiness_snapshots(
                ORGANIZATION_ID,
                COURSE_ID,
                temporary_cohort_id,
                LEARNER_ID,
                limit=1,
                offset=3,
            )
            assert beyond_end == []

            for org, course, cohort, learner in [
                (
                    OTHER_ORGANIZATION_ID,
                    COURSE_ID,
                    temporary_cohort_id,
                    LEARNER_ID,
                ),
                (
                    ORGANIZATION_ID,
                    UNKNOWN_ID,
                    temporary_cohort_id,
                    LEARNER_ID,
                ),
                (
                    ORGANIZATION_ID,
                    COURSE_ID,
                    UNKNOWN_ID,
                    LEARNER_ID,
                ),
                (
                    ORGANIZATION_ID,
                    COURSE_ID,
                    temporary_cohort_id,
                    TUTOR_ID,
                ),
            ]:
                assert repository.list_readiness_snapshots(
                    org, course, cohort, learner
                ) == []

        finally:
            transaction.rollback()
