"""Authentication and authorization API schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from skillpulse.db.identity import MembershipRole


class OrganizationMembershipResponse(BaseModel):
    """An active organisation role visible to the authenticated user."""

    organization_id: UUID
    organization_name: str
    organization_slug: str
    role: MembershipRole

    model_config = ConfigDict(from_attributes=True)


class CurrentUserResponse(BaseModel):
    """The authenticated SkillPulse user and authorized memberships."""

    user_id: UUID
    email: str
    full_name: str
    memberships: list[OrganizationMembershipResponse]

    model_config = ConfigDict(from_attributes=True)
