"""Tests for attendance and understanding API schemas."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from skillpulse.schemas.session_engagement import (
    AttendanceRecordResponse,
    AttendanceRosterItem,
    AttendanceStatus,
    AttendanceUpsert,
    UnderstandingCheckResponse,
    UnderstandingCheckUpsert,
    UnderstandingRating,
    UnderstandingRosterItem,
)

_SESSION_ID = "50000000-0000-0000-0000-000000000001"
_LEARNER_ID = "20000000-0000-0000-0000-000000000003"
_TUTOR_ID = "20000000-0000-0000-0000-000000000002"


def test_attendance_upsert_accepts_valid_payload() -> None:
    attendance = AttendanceUpsert.model_validate(
        {
            "attendance_status": "present",
            "minutes_attended": 120,
        }
    )

    assert attendance.attendance_status is AttendanceStatus.PRESENT
    assert attendance.minutes_attended == 120


def test_attendance_upsert_allows_unknown_minutes() -> None:
    attendance = AttendanceUpsert.model_validate(
        {
            "attendance_status": "excused",
            "minutes_attended": None,
        }
    )

    assert attendance.attendance_status is AttendanceStatus.EXCUSED
    assert attendance.minutes_attended is None


def test_attendance_upsert_rejects_negative_minutes() -> None:
    with pytest.raises(ValidationError):
        AttendanceUpsert.model_validate(
            {
                "attendance_status": "late",
                "minutes_attended": -1,
            }
        )


def test_attendance_upsert_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        AttendanceUpsert.model_validate(
            {
                "attendance_status": "partially-present",
                "minutes_attended": 30,
            }
        )


def test_attendance_upsert_rejects_unknown_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        AttendanceUpsert.model_validate(
            {
                "attendance_status": "present",
                "minutes_attended": 120,
                "learner_id": _LEARNER_ID,
            }
        )


def test_understanding_upsert_accepts_and_strips_comment() -> None:
    check = UnderstandingCheckUpsert.model_validate(
        {
            "rating": "yellow",
            "comment": "  Needs more S3 practice.  ",
        }
    )

    assert check.rating is UnderstandingRating.YELLOW
    assert check.comment == "Needs more S3 practice."


def test_understanding_upsert_allows_missing_comment() -> None:
    check = UnderstandingCheckUpsert.model_validate(
        {
            "rating": "green",
        }
    )

    assert check.rating is UnderstandingRating.GREEN
    assert check.comment is None


def test_understanding_upsert_rejects_unknown_rating() -> None:
    with pytest.raises(ValidationError):
        UnderstandingCheckUpsert.model_validate(
            {
                "rating": "blue",
            }
        )


@pytest.mark.parametrize(
    "comment",
    [
        "",
        "   ",
        "x" * 2001,
    ],
)
def test_understanding_upsert_rejects_invalid_comment(
    comment: str,
) -> None:
    with pytest.raises(ValidationError):
        UnderstandingCheckUpsert.model_validate(
            {
                "rating": "red",
                "comment": comment,
            }
        )


def test_understanding_upsert_rejects_unknown_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        UnderstandingCheckUpsert.model_validate(
            {
                "rating": "green",
                "learner_id": _LEARNER_ID,
            }
        )


def test_attendance_response_validates_database_record() -> None:
    recorded_at = datetime(2026, 8, 5, 11, 5, tzinfo=UTC)
    attendance = AttendanceRecordResponse.model_validate(
        {
            "id": "51000000-0000-0000-0000-000000000001",
            "session_id": _SESSION_ID,
            "learner_id": _LEARNER_ID,
            "email": "learner@example.com",
            "full_name": "Synthetic Learner",
            "attendance_status": "present",
            "minutes_attended": 120,
            "recorded_by": _TUTOR_ID,
            "recorded_at": recorded_at,
            "created_at": recorded_at,
            "updated_at": recorded_at,
        }
    )

    assert attendance.session_id == UUID(_SESSION_ID)
    assert attendance.learner_id == UUID(_LEARNER_ID)
    assert attendance.attendance_status is AttendanceStatus.PRESENT
    assert attendance.recorded_by == UUID(_TUTOR_ID)


def test_attendance_roster_accepts_unrecorded_learner() -> None:
    item = AttendanceRosterItem.model_validate(
        {
            "session_id": _SESSION_ID,
            "learner_id": _LEARNER_ID,
            "email": "learner@example.com",
            "full_name": "Synthetic Learner",
            "attendance_id": None,
            "attendance_status": None,
            "minutes_attended": None,
            "recorded_by": None,
            "recorded_at": None,
        }
    )

    assert item.attendance_id is None
    assert item.attendance_status is None


def test_understanding_response_validates_database_record() -> None:
    submitted_at = datetime(2026, 8, 12, 11, 10, tzinfo=UTC)
    check = UnderstandingCheckResponse.model_validate(
        {
            "id": "52000000-0000-0000-0000-000000000002",
            "session_id": _SESSION_ID,
            "learner_id": _LEARNER_ID,
            "email": "learner@example.com",
            "full_name": "Synthetic Learner",
            "rating": "yellow",
            "confidence_score": 60,
            "comment": "Needs more S3 practice.",
            "submitted_at": submitted_at,
            "created_at": submitted_at,
            "updated_at": submitted_at,
        }
    )

    assert check.rating is UnderstandingRating.YELLOW
    assert check.confidence_score == 60
    assert check.learner_id == UUID(_LEARNER_ID)


def test_understanding_roster_accepts_unsubmitted_learner() -> None:
    item = UnderstandingRosterItem.model_validate(
        {
            "session_id": _SESSION_ID,
            "learner_id": _LEARNER_ID,
            "email": "learner@example.com",
            "full_name": "Synthetic Learner",
            "understanding_check_id": None,
            "rating": None,
            "confidence_score": None,
            "comment": None,
            "submitted_at": None,
        }
    )

    assert item.understanding_check_id is None
    assert item.rating is None
