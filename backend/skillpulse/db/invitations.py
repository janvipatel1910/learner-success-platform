"""Organisation invitation and first sign-in activation database operations."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from skillpulse.db.connection import get_engine
from skillpulse.db.identity import MembershipRole


class UserAlreadyExistsError(Exception):
    """Raised when an invited email or Cognito subject already belongs to a user."""


class CohortNotFoundError(Exception):
    """Raised when the chosen cohort does not belong to the inviting organisation."""


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

_INSERT_INVITED_COHORT_MEMBERSHIP = text(
    """
    INSERT INTO cohort_memberships (
        cohort_id,
        user_id,
        cohort_role,
        status
    )
    SELECT
        h.id,
        :user_id,
        CAST(:cohort_role AS cohort_role),
        'invited'
    FROM cohorts AS h
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        h.id = :cohort_id
        AND c.organization_id = :organization_id
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

_ACTIVATE_INVITED_COHORT_MEMBERSHIPS = text(
    """
    UPDATE cohort_memberships
    SET
        status = 'active',
        enrolled_at = NOW(),
        updated_at = NOW()
    WHERE
        user_id = :user_id
        AND status = 'invited'
    """
)

# Admins run the organisation; only learners and tutors are placed in a cohort.
_COHORT_ROLE_FOR = {
    MembershipRole.STUDENT: "learner",
    MembershipRole.TUTOR: "tutor",
}


def create_invitation(
    *,
    organization_id: UUID,
    email: str,
    full_name: str,
    role: MembershipRole,
    auth_subject: str,
    cohort_id: UUID | None = None,
) -> CreatedInvitation:
    """Create an invited user, their organisation membership and optional cohort place.

    All rows are written in one transaction, so either all exist or none do.
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

            cohort_role = _COHORT_ROLE_FOR.get(role)
            if cohort_id is not None and cohort_role is not None:
                cohort_membership_id = connection.execute(
                    _INSERT_INVITED_COHORT_MEMBERSHIP,
                    {
                        "cohort_id": cohort_id,
                        "organization_id": organization_id,
                        "user_id": user_id,
                        "cohort_role": cohort_role,
                    },
                ).scalar_one_or_none()

                if cohort_membership_id is None:
                    # Raising here rolls back the user and membership rows too.
                    raise CohortNotFoundError(str(cohort_id))
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
        connection.execute(
            _ACTIVATE_INVITED_COHORT_MEMBERSHIPS,
            {"user_id": user_id},
        )

    return True
