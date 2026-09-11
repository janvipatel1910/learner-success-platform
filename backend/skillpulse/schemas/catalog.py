"""Validated API schemas for courses, topics and cohorts."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CourseStatus(StrEnum):
    """Supported course lifecycle states."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class CohortStatus(StrEnum):
    """Supported cohort lifecycle states."""

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"


class DeliveryMode(StrEnum):
    """Supported cohort delivery modes."""

    ONLINE = "online"
    CLASSROOM = "classroom"
    HYBRID = "hybrid"


class CatalogPayload(BaseModel):
    """Strict shared validation for catalog write payloads."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class CoursePayload(CatalogPayload):
    """Fields required to define a course."""

    title: str = Field(min_length=1, max_length=200)
    code: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    description: str | None = Field(default=None, max_length=5000)
    certification_name: str | None = Field(default=None, max_length=150)
    status: CourseStatus


class CourseCreate(CoursePayload):
    """Create a new organisation course."""

    status: CourseStatus = CourseStatus.DRAFT


class CourseUpdate(CoursePayload):
    """Fully replace editable course fields."""


class CourseResponse(CoursePayload):
    """Course data returned by the API."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopicPayload(CatalogPayload):
    """Fields required to define a course topic."""

    title: str = Field(min_length=1, max_length=200)
    sequence_number: int = Field(ge=1)
    exam_domain: str | None = Field(default=None, max_length=150)
    expected_hours: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=5,
        decimal_places=2,
    )


class TopicCreate(TopicPayload):
    """Create a topic inside an organisation-owned course."""


class TopicUpdate(TopicPayload):
    """Fully replace editable topic fields."""


class TopicResponse(TopicPayload):
    """Topic data returned by the API."""

    id: UUID
    course_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CohortPayload(CatalogPayload):
    """Fields required to define a delivery cohort."""

    name: str = Field(min_length=1, max_length=150)
    start_date: date
    end_date: date | None = None
    delivery_mode: DeliveryMode
    status: CohortStatus

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        """Reject a cohort ending before its start date."""

        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")

        return self


class CohortCreate(CohortPayload):
    """Create a cohort inside an organisation-owned course."""

    status: CohortStatus = CohortStatus.PLANNED


class CohortUpdate(CohortPayload):
    """Fully replace editable cohort fields."""


class CohortResponse(CohortPayload):
    """Cohort data returned by the API."""

    id: UUID
    course_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse[ItemT](BaseModel):
    """A deterministic offset-paginated API response."""

    items: list[ItemT]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
