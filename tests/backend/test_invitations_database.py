import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from scripts.seed_synthetic_data import load_synthetic_data
from sqlalchemy import text

from skillpulse.db.connection import get_engine
from skillpulse.db.identity import MembershipRole, find_active_user_by_subject
from skillpulse.db.invitations import (
    CohortNotFoundError,
    UserAlreadyExistsError,
    activate_invited_user,
    create_invitation,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_TESTS") != "true",
        reason="Set RUN_DATABASE_TESTS=true to run PostgreSQL integration tests",
    ),
]

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")


@pytest.fixture(scope="module", autouse=True)
def synthetic_data() -> None:
    load_synthetic_data()


@pytest.fixture(autouse=True)
def remove_test_invites() -> Iterator[None]:
    """Delete the users these tests create, so other tests see only the seed data."""

    yield
    with get_engine().begin() as connection:
        for table in ("cohort_memberships", "organization_memberships"):
            connection.execute(
                text(
                    f"DELETE FROM {table} WHERE user_id IN "
                    "(SELECT id FROM users WHERE email LIKE 'invite.%@example.com')"
                )
            )
        connection.execute(text("DELETE FROM users WHERE email LIKE 'invite.%@example.com'"))


def _unique_email() -> str:
    return f"invite.{uuid4().hex[:10]}@example.com"


def _statuses(user_id: UUID) -> tuple[str, str, str | None]:
    with get_engine().connect() as connection:
        return connection.execute(
            text(
                """
                SELECT
                    u.status::TEXT,
                    om.status::TEXT,
                    cm.status::TEXT
                FROM users AS u
                JOIN organization_memberships AS om
                    ON om.user_id = u.id
                LEFT JOIN cohort_memberships AS cm
                    ON cm.user_id = u.id
                WHERE u.id = :user_id
                """
            ),
            {"user_id": user_id},
        ).one()


def test_invited_learner_is_activated_with_cohort_place_on_first_sign_in() -> None:
    subject = f"subject-{uuid4()}"
    invitation = create_invitation(
        organization_id=ORGANIZATION_ID,
        email=_unique_email(),
        full_name="Invited Learner",
        role=MembershipRole.STUDENT,
        auth_subject=subject,
        cohort_id=COHORT_ID,
    )

    assert _statuses(invitation.user_id) == ("invited", "invited", "invited")
    assert find_active_user_by_subject(subject) is None

    assert activate_invited_user(subject) is True

    assert _statuses(invitation.user_id) == ("active", "active", "active")
    user = find_active_user_by_subject(subject)
    assert user is not None
    assert user.roles_for(ORGANIZATION_ID) == {MembershipRole.STUDENT}


def test_activation_only_happens_once() -> None:
    subject = f"subject-{uuid4()}"
    create_invitation(
        organization_id=ORGANIZATION_ID,
        email=_unique_email(),
        full_name="Invited Once",
        role=MembershipRole.STUDENT,
        auth_subject=subject,
    )

    assert activate_invited_user(subject) is True
    assert activate_invited_user(subject) is False
    assert activate_invited_user("unknown-subject") is False


def test_admin_invite_is_not_placed_in_a_cohort() -> None:
    invitation = create_invitation(
        organization_id=ORGANIZATION_ID,
        email=_unique_email(),
        full_name="Invited Admin",
        role=MembershipRole.ADMIN,
        auth_subject=f"subject-{uuid4()}",
        cohort_id=COHORT_ID,
    )

    assert _statuses(invitation.user_id) == ("invited", "invited", None)


def test_unknown_cohort_saves_nothing() -> None:
    email = _unique_email()

    with pytest.raises(CohortNotFoundError):
        create_invitation(
            organization_id=ORGANIZATION_ID,
            email=email,
            full_name="Wrong Cohort",
            role=MembershipRole.STUDENT,
            auth_subject=f"subject-{uuid4()}",
            cohort_id=uuid4(),
        )

    with get_engine().connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM users WHERE email = :email"),
            {"email": email},
        ).scalar_one()
    assert count == 0


def test_duplicate_email_is_rejected() -> None:
    email = _unique_email()
    create_invitation(
        organization_id=ORGANIZATION_ID,
        email=email,
        full_name="First Invite",
        role=MembershipRole.STUDENT,
        auth_subject=f"subject-{uuid4()}",
    )

    with pytest.raises(UserAlreadyExistsError):
        create_invitation(
            organization_id=ORGANIZATION_ID,
            email=email,
            full_name="Second Invite",
            role=MembershipRole.STUDENT,
            auth_subject=f"subject-{uuid4()}",
        )
