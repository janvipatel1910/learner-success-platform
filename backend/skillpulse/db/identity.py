"""Database-backed user and organisation identity resolution."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy import text

from skillpulse.db.connection import get_engine


class MembershipRole(StrEnum):
    """Supported organisation-level authorization roles."""

    STUDENT = "student"
    TUTOR = "tutor"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class OrganizationMembership:
    """An active role held by a user in an active organisation."""

    organization_id: UUID
    organization_name: str
    organization_slug: str
    role: MembershipRole


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """An active SkillPulse user and their active memberships."""

    user_id: UUID
    email: str
    full_name: str
    memberships: tuple[OrganizationMembership, ...]

    def roles_for(self, organization_id: UUID) -> frozenset[MembershipRole]:
        """Return all active roles held in one organisation."""

        return frozenset(
            membership.role
            for membership in self.memberships
            if membership.organization_id == organization_id
        )


_ACTIVE_USER_QUERY = text(
    """
    SELECT
        u.id AS user_id,
        u.email::TEXT AS email,
        u.full_name,
        o.id AS organization_id,
        o.name AS organization_name,
        o.slug::TEXT AS organization_slug,
        om.role::TEXT AS role
    FROM users AS u
    JOIN organization_memberships AS om
        ON om.user_id = u.id
       AND om.status = 'active'
    JOIN organizations AS o
        ON o.id = om.organization_id
       AND o.status IN ('pilot', 'active')
    WHERE
        u.auth_subject = :auth_subject
        AND u.status = 'active'
    ORDER BY
        o.name,
        om.role::TEXT
    """
)


def find_active_user_by_subject(
    auth_subject: str,
) -> AuthenticatedUser | None:
    """Find an active user and all authorized organisation memberships."""

    with get_engine().connect() as connection:
        rows = (
            connection.execute(
                _ACTIVE_USER_QUERY,
                {"auth_subject": auth_subject},
            )
            .mappings()
            .all()
        )

    if not rows:
        return None

    first_row = rows[0]
    memberships = tuple(
        OrganizationMembership(
            organization_id=row["organization_id"],
            organization_name=row["organization_name"],
            organization_slug=row["organization_slug"],
            role=MembershipRole(row["role"]),
        )
        for row in rows
    )

    return AuthenticatedUser(
        user_id=first_row["user_id"],
        email=first_row["email"],
        full_name=first_row["full_name"],
        memberships=memberships,
    )
