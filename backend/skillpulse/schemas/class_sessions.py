"""Validated API schemas for class-session management."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionStatus(StrEnum):
    """Supported class-session lifecycle states."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ClassSessionPayload(BaseModel):
    """Strict shared validation for class-session writes."""

    topic_id: UUID
    title: str = Field(min_length=1, max_length=200)
    scheduled_start: datetime
    scheduled_end: datetime
    delivery_link: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        pattern=r"^https?://\S+$",
    )
    recording_url: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        pattern=r"^https?://\S+$",
    )
    status: SessionStatus

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        """Require timezone-aware timestamps and a positive duration."""

        if (
            self.scheduled_start.tzinfo is None
            or self.scheduled_start.utcoffset() is None
            or self.scheduled_end.tzinfo is None
            or self.scheduled_end.utcoffset() is None
        ):
            raise ValueError(
                "scheduled_start and scheduled_end must include a timezone."
            )

        if self.scheduled_end <= self.scheduled_start:
            raise ValueError(
                "scheduled_end must be after scheduled_start."
            )

        return self


class ClassSessionCreate(ClassSessionPayload):
    """Create a class session inside an authorised cohort."""

    status: SessionStatus = SessionStatus.SCHEDULED


class ClassSessionUpdate(ClassSessionPayload):
    """Fully replace editable class-session fields."""


class ClassSessionResponse(ClassSessionPayload):
    """Class-session data returned by the API."""

    id: UUID
    cohort_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
