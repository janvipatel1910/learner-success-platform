"""PostgreSQL integration tests for class-session operations."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from scripts.seed_synthetic_data import load_synthetic_data
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from skillpulse.db import class_sessions as session_repository
from skillpulse.db import cohort_memberships as membership_repository
from skillpulse.db.connection import get_engine
from skillpulse.schemas.class_sessions import (
    ClassSessionCreate,
    ClassSessionUpdate,
    SessionStatus,
)
from skillpulse.schemas.enrollment import CohortRole

pytestmark = pytest.mark.integration

requires_database = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run PostgreSQL integration tests",
)

requires_seed_tests = pytest.mark.skipif(
    os.getenv("RUN_SEED_TESTS") != "true",
    reason="Set RUN_SEED_TESTS=true to run synthetic seed tests",
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")
TOPIC_ID = UUID("41000000-0000-0000-0000-000000000001")
SEEDED_SESSION_ID = UUID(
    "50000000-0000-0000-0000-000000000001"
)
TUTOR_USER_ID = UUID("20000000-0000-0000-0000-000000000002")
LEARNER_USER_ID = UUID(
    "20000000-0000-0000-0000-000000000003"
)


def unique_schedule() -> tuple[datetime, datetime]:
    """Return a collision-resistant future session time range."""

    scheduled_start = datetime.now(UTC) + timedelta(days=3650)
    scheduled_start = scheduled_start.replace(
        microsecond=uuid4().int % 1_000_000
    )
    return scheduled_start, scheduled_start + timedelta(hours=2)


def delete_class_session(session_id: UUID | None) -> None:
    """Remove a temporary class session created by a test."""

    if session_id is None:
        return

    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                DELETE FROM class_sessions
                WHERE id = :session_id
                """
            ),
            {"session_id": session_id},
        )


@requires_database
@requires_seed_tests
def test_seeded_sessions_and_cohort_roles_are_scoped() -> None:
    """Read seeded sessions and roles without cross-organisation leakage."""

    load_synthetic_data()

    sessions, total = session_repository.list_class_sessions(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        limit=20,
        offset=0,
    )

    assert total >= 2
    assert SEEDED_SESSION_ID in {
        class_session.id
        for class_session in sessions
    }
    session_keys = [
        (class_session.scheduled_start, class_session.id)
        for class_session in sessions
    ]
    assert session_keys == sorted(session_keys)

    class_session = session_repository.get_class_session(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        SEEDED_SESSION_ID,
    )
    assert class_session is not None
    assert class_session.title == "VPC Foundations"
    assert class_session.status is SessionStatus.COMPLETED

    hidden_sessions, hidden_total = (
        session_repository.list_class_sessions(
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            limit=20,
            offset=0,
        )
    )
    assert hidden_sessions == []
    assert hidden_total == 0
    assert (
        session_repository.get_class_session(
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
        )
        is None
    )

    assert membership_repository.has_active_cohort_role(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        TUTOR_USER_ID,
        CohortRole.TUTOR,
    )
    assert membership_repository.has_active_cohort_role(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        LEARNER_USER_ID,
        CohortRole.LEARNER,
    )
    assert not membership_repository.has_active_cohort_role(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        LEARNER_USER_ID,
        CohortRole.TUTOR,
    )


@requires_database
@requires_seed_tests
def test_create_and_update_class_session() -> None:
    """Create, retrieve and update one fully scoped class session."""

    load_synthetic_data()
    scheduled_start, scheduled_end = unique_schedule()
    session_id: UUID | None = None

    try:
        created = session_repository.create_class_session(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            ClassSessionCreate(
                topic_id=TOPIC_ID,
                title="SC-008 Temporary Session",
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                delivery_link="https://meet.example.com/sc008",
            ),
        )

        assert created is not None
        session_id = created.id
        assert created.cohort_id == COHORT_ID
        assert created.topic_id == TOPIC_ID
        assert created.status is SessionStatus.SCHEDULED

        fetched = session_repository.get_class_session(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            session_id,
        )
        assert fetched is not None
        assert fetched.id == session_id

        updated = session_repository.update_class_session(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            session_id,
            ClassSessionUpdate(
                topic_id=TOPIC_ID,
                title="SC-008 Completed Session",
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                delivery_link="https://meet.example.com/sc008",
                recording_url=(
                    "https://recordings.example.com/sc008"
                ),
                status=SessionStatus.COMPLETED,
            ),
        )

        assert updated is not None
        assert updated.id == session_id
        assert updated.title == "SC-008 Completed Session"
        assert updated.status is SessionStatus.COMPLETED
        assert updated.recording_url == (
            "https://recordings.example.com/sc008"
        )
        assert updated.updated_at >= created.updated_at

        assert (
            session_repository.get_class_session(
                OTHER_ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
            )
            is None
        )
    finally:
        delete_class_session(session_id)


@requires_database
@requires_seed_tests
def test_invalid_session_parents_do_not_create_or_update() -> None:
    """Reject unscoped cohorts and topics from another course context."""

    load_synthetic_data()
    scheduled_start, scheduled_end = unique_schedule()
    missing_topic_id = uuid4()

    invalid_create = ClassSessionCreate(
        topic_id=missing_topic_id,
        title="Invalid Parent Session",
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
    )

    assert (
        session_repository.create_class_session(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            invalid_create,
        )
        is None
    )
    assert (
        session_repository.create_class_session(
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            ClassSessionCreate(
                topic_id=TOPIC_ID,
                title="Cross-organisation Session",
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
            ),
        )
        is None
    )

    invalid_update = ClassSessionUpdate(
        topic_id=missing_topic_id,
        title="Invalid Topic Update",
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        status=SessionStatus.SCHEDULED,
    )
    assert (
        session_repository.update_class_session(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
            invalid_update,
        )
        is None
    )


@requires_database
@requires_seed_tests
def test_duplicate_cohort_start_time_is_rejected() -> None:
    """Enforce one class-session start time per cohort."""

    load_synthetic_data()
    scheduled_start, scheduled_end = unique_schedule()
    session_id: UUID | None = None

    try:
        created = session_repository.create_class_session(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            ClassSessionCreate(
                topic_id=TOPIC_ID,
                title="Unique Scheduled Session",
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
            ),
        )
        assert created is not None
        session_id = created.id

        with pytest.raises(IntegrityError):
            session_repository.create_class_session(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                ClassSessionCreate(
                    topic_id=TOPIC_ID,
                    title="Duplicate Scheduled Session",
                    scheduled_start=scheduled_start,
                    scheduled_end=scheduled_end,
                ),
            )
    finally:
        delete_class_session(session_id)
