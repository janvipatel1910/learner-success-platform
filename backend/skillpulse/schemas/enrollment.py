"""Validated API schemas for cohort enrollment and roster management."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CohortRole(StrEnum):
    """Supported roles held inside a cohort."""

    LEARNER = "learner"
    TUTOR = "tutor"


class CohortMembershipStatus(StrEnum):
    """Supported cohort-membership lifecycle states."""

    INVITED = "invited"
    ACTIVE = "active"
    INACTIVE = "inactive"


class CohortMembershipPayload(BaseModel):
    """Strict shared validation for cohort-membership writes."""

    cohort_role: CohortRole
    status: CohortMembershipStatus

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class CohortMembershipCreate(CohortMembershipPayload):
    """Enroll an organisation member in a cohort."""

    user_id: UUID
    status: CohortMembershipStatus = CohortMembershipStatus.ACTIVE


class CohortMembershipUpdate(CohortMembershipPayload):
    """Fully replace a cohort member's role and status."""


class CohortMembershipResponse(CohortMembershipPayload):
    """Roster membership returned to an administrator or assigned tutor."""

    id: UUID
    cohort_id: UUID
    user_id: UUID
    email: str
    full_name: str
    enrolled_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MyCohortMembershipResponse(BaseModel):
    """One cohort membership visible to its authenticated owner."""

    id: UUID
    course_id: UUID
    course_title: str
    cohort_id: UUID
    cohort_name: str
    cohort_role: CohortRole
    status: CohortMembershipStatus
    start_date: date
    end_date: date | None
    enrolled_at: datetime

    model_config = ConfigDict(from_attributes=True)
