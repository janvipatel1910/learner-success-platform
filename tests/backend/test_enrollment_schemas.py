from uuid import UUID

import pytest
from pydantic import ValidationError

from skillpulse.schemas.enrollment import (
    CohortMembershipCreate,
    CohortMembershipStatus,
    CohortMembershipUpdate,
    CohortRole,
)

USER_ID = UUID("20000000-0000-0000-0000-000000000001")


def test_membership_create_defaults_to_active() -> None:
    membership = CohortMembershipCreate(
        user_id=USER_ID,
        cohort_role="learner",
    )

    assert membership.user_id == USER_ID
    assert membership.cohort_role is CohortRole.LEARNER
    assert membership.status is CohortMembershipStatus.ACTIVE


def test_membership_create_accepts_controlled_status() -> None:
    membership = CohortMembershipCreate(
        user_id=USER_ID,
        cohort_role="tutor",
        status="invited",
    )

    assert membership.cohort_role is CohortRole.TUTOR
    assert membership.status is CohortMembershipStatus.INVITED


@pytest.mark.parametrize(
    "payload",
    [
        {
            "user_id": str(USER_ID),
            "cohort_role": "student",
        },
        {
            "user_id": str(USER_ID),
            "cohort_role": "learner",
            "status": "suspended",
        },
        {
            "user_id": "not-a-uuid",
            "cohort_role": "learner",
        },
    ],
)
def test_membership_create_rejects_invalid_values(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CohortMembershipCreate.model_validate(payload)


def test_membership_payload_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CohortMembershipCreate.model_validate(
            {
                "user_id": str(USER_ID),
                "cohort_role": "learner",
                "organization_id": (
                    "10000000-0000-0000-0000-000000000001"
                ),
            }
        )


def test_membership_update_requires_role_and_status() -> None:
    with pytest.raises(ValidationError):
        CohortMembershipUpdate.model_validate(
            {
                "cohort_role": "tutor",
            }
        )
