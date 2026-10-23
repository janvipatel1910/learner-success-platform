"""Organisation invitation and first sign-in activation database operations."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from skillpulse.db.connection import get_engine
from skillpulse.db.identity import MembershipRole


class UserAlreadyExistsError(Exception):
    """Raised when an invited email or Cognito subject already belongs to a user."""


@dataclass(frozen=True, slots=True)
class CreatedInvitation:
    """The database rows created for one invitation."""

    user_id: UUID
    membership_id: UUID


_INSERT_INVITED_USER = text(
    """
    INSERT INTO users (
        auth_subject,
        email,
        full_name,
        status
    )
    VALUES (
        :auth_subject,
        :email,
        :full_name,
        'invited'
    )
    RETURNING id
    """
)

_INSERT_INVITED_MEMBERSHIP = text(
    """
    INSERT INTO organization_memberships (
        organization_id,
        user_id,
        role,
        status
    )
    VALUES (
        :organization_id,
        :user_id,
        CAST(:role AS membership_role),
        'invited'
    )
    RETURNING id
    """
)

_ACTIVATE_INVITED_USER = text(
    """
    UPDATE users
    SET
        status = 'active',
        last_login_at = NOW(),
        updated_at = NOW()
    WHERE
        auth_subject = :auth_subject
        AND status = 'invited'
    RETURNING id
    """
)

_ACTIVATE_INVITED_MEMBERSHIPS = text(
    """
    UPDATE organization_memberships
    SET
        status = 'active',
        joined_at = NOW(),
        updated_at = NOW()
    WHERE
        user_id = :user_id
        AND status = 'invited'
    """
)


def create_invitation(
    *,
    organization_id: UUID,
    email: str,
    full_name: str,
    role: MembershipRole,
    auth_subject: str,
) -> CreatedInvitation:
    """Create an invited user and their invited organisation membership.

    Both rows are written in one transaction, so either both exist or neither does.
    """

    try:
        with get_engine().begin() as connection:
            user_id = connection.execute(
                _INSERT_INVITED_USER,
                {
                    "auth_subject": auth_subject,
                    "email": email,
                    "full_name": full_name,
                },
            ).scalar_one()

            membership_id = connection.execute(
                _INSERT_INVITED_MEMBERSHIP,
                {
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "role": role.value,
                },
            ).scalar_one()
    except IntegrityError as exc:
        raise UserAlreadyExistsError(email) from exc

    return CreatedInvitation(user_id=user_id, membership_id=membership_id)


def activate_invited_user(auth_subject: str) -> bool:
    """Activate an invited user and their memberships on first sign-in.

    Returns True if an invited user was activated, otherwise False.
    """

    with get_engine().begin() as connection:
        user_id = connection.execute(
            _ACTIVATE_INVITED_USER,
            {"auth_subject": auth_subject},
        ).scalar_one_or_none()

        if user_id is None:
            return False

        connection.execute(
            _ACTIVATE_INVITED_MEMBERSHIPS,
            {"user_id": user_id},
        )

    return True
