"""PostgreSQL integration tests for session-engagement operations."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from scripts.seed_synthetic_data import load_synthetic_data
from sqlalchemy import text

from skillpulse.db import class_sessions as session_repository
from skillpulse.db import session_engagement as engagement_repository
from skillpulse.db.connection import get_engine
from skillpulse.schemas.class_sessions import (
    ClassSessionCreate,
    SessionStatus,
)
from skillpulse.schemas.session_engagement import (
    AttendanceStatus,
    AttendanceUpsert,
    UnderstandingCheckUpsert,
    UnderstandingRating,
)

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


def create_temporary_session(
    session_status: SessionStatus,
) -> UUID:
    """Create one temporary scoped class session."""

    scheduled_start, scheduled_end = unique_schedule()
    class_session = session_repository.create_class_session(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        ClassSessionCreate(
            topic_id=TOPIC_ID,
            title=f"SC-009 Temporary Session {uuid4()}",
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            status=session_status,
        ),
    )

    assert class_session is not None
    return class_session.id


def delete_class_session(session_id: UUID | None) -> None:
    """Delete a temporary session and its cascading engagement data."""

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
def test_seeded_engagement_records_are_scoped() -> None:
    """Read seeded engagement without cross-organisation leakage."""

    load_synthetic_data()

    attendance, attendance_total = (
        engagement_repository.list_session_attendance(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
            limit=20,
            offset=0,
        )
    )

    assert attendance_total >= 2
    learner_attendance = next(
        item
        for item in attendance
        if item.learner_id == LEARNER_USER_ID
    )
    assert learner_attendance.attendance_status is (
        AttendanceStatus.PRESENT
    )
    assert learner_attendance.minutes_attended == 120

    attendance_record = (
        engagement_repository.get_session_attendance(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
            LEARNER_USER_ID,
        )
    )
    assert attendance_record is not None
    assert attendance_record.attendance_status is (
        AttendanceStatus.PRESENT
    )

    checks, checks_total = (
        engagement_repository.list_session_understanding(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
            limit=20,
            offset=0,
        )
    )

    assert checks_total >= 2
    learner_check = next(
        item
        for item in checks
        if item.learner_id == LEARNER_USER_ID
    )
    assert learner_check.rating is UnderstandingRating.GREEN
    assert learner_check.confidence_score == 100

    understanding_record = (
        engagement_repository.get_session_understanding(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
            LEARNER_USER_ID,
        )
    )
    assert understanding_record is not None
    assert understanding_record.rating is UnderstandingRating.GREEN
    assert understanding_record.confidence_score == 100

    hidden_attendance, hidden_attendance_total = (
        engagement_repository.list_session_attendance(
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
            limit=20,
            offset=0,
        )
    )
    assert hidden_attendance == []
    assert hidden_attendance_total == 0

    hidden_checks, hidden_checks_total = (
        engagement_repository.list_session_understanding(
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
            limit=20,
            offset=0,
        )
    )
    assert hidden_checks == []
    assert hidden_checks_total == 0

    assert (
        engagement_repository.get_session_attendance(
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
            LEARNER_USER_ID,
        )
        is None
    )
    assert (
        engagement_repository.get_session_understanding(
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            SEEDED_SESSION_ID,
            LEARNER_USER_ID,
        )
        is None
    )


@requires_database
@requires_seed_tests
def test_completed_session_engagement_is_upserted() -> None:
    """Create and update attendance and understanding atomically."""

    load_synthetic_data()
    session_id: UUID | None = None

    try:
        session_id = create_temporary_session(
            SessionStatus.COMPLETED
        )

        attendance, attendance_total = (
            engagement_repository.list_session_attendance(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                limit=20,
                offset=0,
            )
        )
        assert attendance_total >= 2
        unrecorded_attendance = next(
            item
            for item in attendance
            if item.learner_id == LEARNER_USER_ID
        )
        assert unrecorded_attendance.attendance_id is None
        assert unrecorded_attendance.attendance_status is None

        checks, checks_total = (
            engagement_repository.list_session_understanding(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                limit=20,
                offset=0,
            )
        )
        assert checks_total >= 2
        unsubmitted_check = next(
            item
            for item in checks
            if item.learner_id == LEARNER_USER_ID
        )
        assert unsubmitted_check.understanding_check_id is None
        assert unsubmitted_check.rating is None

        created_attendance = (
            engagement_repository.upsert_session_attendance(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
                TUTOR_USER_ID,
                AttendanceUpsert(
                    attendance_status=AttendanceStatus.LATE,
                    minutes_attended=75,
                ),
            )
        )
        assert created_attendance is not None
        assert created_attendance.attendance_status is (
            AttendanceStatus.LATE
        )
        assert created_attendance.minutes_attended == 75
        assert created_attendance.recorded_by == TUTOR_USER_ID

        updated_attendance = (
            engagement_repository.upsert_session_attendance(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
                TUTOR_USER_ID,
                AttendanceUpsert(
                    attendance_status=AttendanceStatus.PRESENT,
                    minutes_attended=115,
                ),
            )
        )
        assert updated_attendance is not None
        assert updated_attendance.id == created_attendance.id
        assert updated_attendance.attendance_status is (
            AttendanceStatus.PRESENT
        )
        assert updated_attendance.minutes_attended == 115

        created_check = (
            engagement_repository.upsert_session_understanding(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
                UnderstandingCheckUpsert(
                    rating=UnderstandingRating.YELLOW,
                    comment="Needs more routing practice.",
                ),
            )
        )
        assert created_check is not None
        assert created_check.rating is UnderstandingRating.YELLOW
        assert created_check.confidence_score == 60

        updated_check = (
            engagement_repository.upsert_session_understanding(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
                UnderstandingCheckUpsert(
                    rating=UnderstandingRating.RED,
                    comment="Still blocked on route selection.",
                ),
            )
        )
        assert updated_check is not None
        assert updated_check.id == created_check.id
        assert updated_check.rating is UnderstandingRating.RED
        assert updated_check.confidence_score == 20

        fetched_attendance = (
            engagement_repository.get_session_attendance(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
            )
        )
        assert fetched_attendance is not None
        assert fetched_attendance.id == created_attendance.id

        fetched_check = (
            engagement_repository.get_session_understanding(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
            )
        )
        assert fetched_check is not None
        assert fetched_check.id == created_check.id

    finally:
        delete_class_session(session_id)


@requires_database
@requires_seed_tests
def test_scheduled_session_rejects_engagement_writes() -> None:
    """Reject attendance and understanding before completion."""

    load_synthetic_data()
    session_id: UUID | None = None

    try:
        session_id = create_temporary_session(
            SessionStatus.SCHEDULED
        )

        assert (
            engagement_repository.upsert_session_attendance(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
                TUTOR_USER_ID,
                AttendanceUpsert(
                    attendance_status=AttendanceStatus.PRESENT,
                    minutes_attended=120,
                ),
            )
            is None
        )

        assert (
            engagement_repository.upsert_session_understanding(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
                UnderstandingCheckUpsert(
                    rating=UnderstandingRating.GREEN,
                ),
            )
            is None
        )

    finally:
        delete_class_session(session_id)


@requires_database
@requires_seed_tests
def test_engagement_writes_enforce_scope_and_eligibility() -> None:
    """Reject invalid organisation, learner and attended duration."""

    load_synthetic_data()
    session_id: UUID | None = None

    try:
        session_id = create_temporary_session(
            SessionStatus.COMPLETED
        )
        attendance_payload = AttendanceUpsert(
            attendance_status=AttendanceStatus.PRESENT,
            minutes_attended=120,
        )
        understanding_payload = UnderstandingCheckUpsert(
            rating=UnderstandingRating.GREEN,
        )

        assert (
            engagement_repository.upsert_session_attendance(
                OTHER_ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
                TUTOR_USER_ID,
                attendance_payload,
            )
            is None
        )

        assert (
            engagement_repository.upsert_session_attendance(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                uuid4(),
                TUTOR_USER_ID,
                attendance_payload,
            )
            is None
        )

        assert (
            engagement_repository.upsert_session_attendance(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
                TUTOR_USER_ID,
                AttendanceUpsert(
                    attendance_status=AttendanceStatus.PRESENT,
                    minutes_attended=121,
                ),
            )
            is None
        )

        assert (
            engagement_repository.upsert_session_understanding(
                OTHER_ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                LEARNER_USER_ID,
                understanding_payload,
            )
            is None
        )

        assert (
            engagement_repository.upsert_session_understanding(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                session_id,
                uuid4(),
                understanding_payload,
            )
            is None
        )

    finally:
        delete_class_session(session_id)
