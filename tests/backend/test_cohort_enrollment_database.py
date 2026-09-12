import os
from uuid import UUID, uuid4

import pytest
from scripts.seed_synthetic_data import load_synthetic_data
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from skillpulse.db import cohort_memberships as membership_repository
from skillpulse.db.connection import get_engine
from skillpulse.schemas.enrollment import (
    CohortMembershipCreate,
    CohortMembershipStatus,
    CohortMembershipUpdate,
    CohortRole,
)

pytestmark = pytest.mark.integration

requires_database = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run PostgreSQL integration tests",
)

requires_seed_tests = pytest.mark.skipif(
    os.getenv("RUN_SEED_TESTS") != "true",
    reason="Set RUN_SEED_TESTS=true to run synthetic seed tests",
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")
TUTOR_USER_ID = UUID("20000000-0000-0000-0000-000000000002")
LEARNER_USER_ID = UUID(
    "20000000-0000-0000-0000-000000000003"
)
TUTOR_MEMBERSHIP_ID = UUID(
    "43000000-0000-0000-0000-000000000001"
)


def create_temporary_student() -> tuple[UUID, UUID]:
    """Create an active student eligible for cohort enrollment."""

    user_id = uuid4()
    organization_membership_id = uuid4()

    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id,
                    auth_subject,
                    email,
                    full_name,
                    status
                )
                VALUES (
                    :user_id,
                    :auth_subject,
                    :email,
                    :full_name,
                    'active'
                )
                """
            ),
            {
                "user_id": user_id,
                "auth_subject": f"sc007-{user_id}",
                "email": f"sc007-{user_id}@skillpulse.example",
                "full_name": "SC-007 Temporary Learner",
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO organization_memberships (
                    id,
                    organization_id,
                    user_id,
                    role,
                    status,
                    joined_at
                )
                VALUES (
                    :membership_id,
                    :organization_id,
                    :user_id,
                    'student',
                    'active',
                    NOW()
                )
                """
            ),
            {
                "membership_id": organization_membership_id,
                "organization_id": ORGANIZATION_ID,
                "user_id": user_id,
            },
        )

    return user_id, organization_membership_id


def delete_temporary_student(user_id: UUID) -> None:
    """Remove all temporary enrollment-test records."""

    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                DELETE FROM cohort_memberships
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        connection.execute(
            text(
                """
                DELETE FROM organization_memberships
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        connection.execute(
            text(
                """
                DELETE FROM users
                WHERE id = :user_id
                """
            ),
            {"user_id": user_id},
        )


@requires_database
@requires_seed_tests
def test_seeded_cohort_membership_queries_are_scoped() -> None:
    """Read the seeded roster without cross-organisation leakage."""

    load_synthetic_data()

    memberships, total = (
        membership_repository.list_cohort_memberships(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            limit=20,
            offset=0,
        )
    )

    assert total >= 3
    assert any(
        item.user_id == TUTOR_USER_ID
        and item.cohort_role is CohortRole.TUTOR
        for item in memberships
    )
    assert any(
        item.user_id == LEARNER_USER_ID
        and item.cohort_role is CohortRole.LEARNER
        for item in memberships
    )

    tutor_membership = (
        membership_repository.get_cohort_membership(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            TUTOR_MEMBERSHIP_ID,
        )
    )

    assert tutor_membership is not None
    assert tutor_membership.user_id == TUTOR_USER_ID
    assert tutor_membership.status is CohortMembershipStatus.ACTIVE

    assert membership_repository.is_active_cohort_tutor(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        TUTOR_USER_ID,
    )
    assert not membership_repository.is_active_cohort_tutor(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        LEARNER_USER_ID,
    )

    own_memberships, own_total = (
        membership_repository.list_my_cohort_memberships(
            ORGANIZATION_ID,
            LEARNER_USER_ID,
            limit=20,
            offset=0,
        )
    )

    assert own_total >= 1
    assert any(
        item.cohort_id == COHORT_ID
        and item.cohort_role is CohortRole.LEARNER
        for item in own_memberships
    )

    other_memberships, other_total = (
        membership_repository.list_cohort_memberships(
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            limit=20,
            offset=0,
        )
    )

    assert other_memberships == []
    assert other_total == 0
    assert (
        membership_repository.get_cohort_membership(
            OTHER_ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            TUTOR_MEMBERSHIP_ID,
        )
        is None
    )



@requires_database
@requires_seed_tests
def test_cohort_membership_create_and_update_lifecycle() -> None:
    """Execute real enrollment SQL and enforce role eligibility."""

    load_synthetic_data()
    user_id, _ = create_temporary_student()

    try:
        rejected_tutor = (
            membership_repository.create_cohort_membership(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                CohortMembershipCreate(
                    user_id=user_id,
                    cohort_role=CohortRole.TUTOR,
                ),
            )
        )
        assert rejected_tutor is None

        created = membership_repository.create_cohort_membership(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            CohortMembershipCreate(
                user_id=user_id,
                cohort_role=CohortRole.LEARNER,
            ),
        )

        assert created is not None
        assert created.user_id == user_id
        assert created.cohort_id == COHORT_ID
        assert created.cohort_role is CohortRole.LEARNER
        assert created.status is CohortMembershipStatus.ACTIVE
        membership_id = created.id

        with pytest.raises(IntegrityError):
            membership_repository.create_cohort_membership(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                CohortMembershipCreate(
                    user_id=user_id,
                    cohort_role=CohortRole.LEARNER,
                ),
            )

        roster, roster_total = (
            membership_repository.list_cohort_memberships(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                limit=100,
                offset=0,
            )
        )
        assert roster_total >= 4
        assert any(
            item.id == membership_id
            and item.user_id == user_id
            for item in roster
        )

        own_memberships, own_total = (
            membership_repository.list_my_cohort_memberships(
                ORGANIZATION_ID,
                user_id,
                limit=20,
                offset=0,
            )
        )
        assert own_total == 1
        assert own_memberships[0].id == membership_id
        assert own_memberships[0].course_id == COURSE_ID
        assert own_memberships[0].cohort_id == COHORT_ID

        assert (
            membership_repository.create_cohort_membership(
                OTHER_ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                CohortMembershipCreate(
                    user_id=user_id,
                    cohort_role=CohortRole.LEARNER,
                ),
            )
            is None
        )
        assert (
            membership_repository.get_cohort_membership(
                OTHER_ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                membership_id,
            )
            is None
        )

        rejected_update = (
            membership_repository.update_cohort_membership(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                membership_id,
                CohortMembershipUpdate(
                    cohort_role=CohortRole.TUTOR,
                    status=CohortMembershipStatus.ACTIVE,
                ),
            )
        )
        assert rejected_update is None

        unchanged = membership_repository.get_cohort_membership(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            membership_id,
        )
        assert unchanged is not None
        assert unchanged.cohort_role is CohortRole.LEARNER
        assert unchanged.status is CohortMembershipStatus.ACTIVE

        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE organization_memberships
                    SET status = 'inactive'
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": user_id},
            )

        deactivated = (
            membership_repository.update_cohort_membership(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                membership_id,
                CohortMembershipUpdate(
                    cohort_role=CohortRole.LEARNER,
                    status=CohortMembershipStatus.INACTIVE,
                ),
            )
        )

        assert deactivated is not None
        assert deactivated.status is CohortMembershipStatus.INACTIVE

        rejected_reactivation = (
            membership_repository.update_cohort_membership(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                membership_id,
                CohortMembershipUpdate(
                    cohort_role=CohortRole.LEARNER,
                    status=CohortMembershipStatus.ACTIVE,
                ),
            )
        )
        assert rejected_reactivation is None

        assert not membership_repository.is_active_cohort_tutor(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            user_id,
        )
    finally:
        delete_temporary_student(user_id)
