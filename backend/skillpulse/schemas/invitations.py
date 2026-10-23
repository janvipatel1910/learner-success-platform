"""Validated API schemas for organisation invitations."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from skillpulse.db.identity import MembershipRole

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class InvitationCreate(BaseModel):
    """An administrator's request to invite one person to the organisation."""

    email: str = Field(min_length=3, max_length=254, pattern=_EMAIL_PATTERN)
    full_name: str = Field(min_length=1, max_length=150)
    role: MembershipRole = MembershipRole.STUDENT
    cohort_id: UUID | None = None

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        """Store emails in lower case so the same person is not invited twice."""

        return value.lower()


class InvitationResponse(BaseModel):
    """The invited user returned after a successful invitation."""

    user_id: UUID
    membership_id: UUID
    email: str
    full_name: str
    role: MembershipRole
    cohort_id: UUID | None = None
    status: Literal["invited"] = "invited"
