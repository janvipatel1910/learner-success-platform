"""Validated API schemas for attendance and understanding workflows."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AttendanceStatus(StrEnum):
    """Supported learner attendance states."""

    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    EXCUSED = "excused"


class UnderstandingRating(StrEnum):
    """Supported post-session understanding ratings."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class AttendanceUpsert(BaseModel):
    """Create or replace one learner's attendance record."""

    attendance_status: AttendanceStatus
    minutes_attended: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class AttendanceRecordResponse(BaseModel):
    """A recorded attendance result returned by the API."""

    id: UUID
    session_id: UUID
    learner_id: UUID
    email: str
    full_name: str
    attendance_status: AttendanceStatus
    minutes_attended: int | None
    recorded_by: UUID | None
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceRosterItem(BaseModel):
    """One learner in a session attendance roster."""

    session_id: UUID
    learner_id: UUID
    email: str
    full_name: str
    attendance_id: UUID | None
    attendance_status: AttendanceStatus | None
    minutes_attended: int | None
    recorded_by: UUID | None
    recorded_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class UnderstandingCheckUpsert(BaseModel):
    """Create or replace the authenticated learner's understanding check."""

    rating: UnderstandingRating
    comment: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class UnderstandingCheckResponse(BaseModel):
    """A learner understanding check returned by the API."""

    id: UUID
    session_id: UUID
    learner_id: UUID
    email: str
    full_name: str
    rating: UnderstandingRating
    confidence_score: int
    comment: str | None
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnderstandingRosterItem(BaseModel):
    """One learner in a session understanding roster."""

    session_id: UUID
    learner_id: UUID
    email: str
    full_name: str
    understanding_check_id: UUID | None
    rating: UnderstandingRating | None
    confidence_score: int | None
    comment: str | None
    submitted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
