import os

import pytest
from scripts.seed_synthetic_data import load_synthetic_data

from skillpulse.db.identity import (
    MembershipRole,
    find_active_user_by_subject,
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

ORGANIZATION_ID = "10000000-0000-0000-0000-000000000001"


@requires_database
@requires_seed_tests
def test_cognito_subject_resolves_database_roles() -> None:
    """Resolve trusted Cognito subjects through active database memberships."""

    load_synthetic_data()

    expected_roles = {
        "a0000000-0000-4000-8000-000000000001": MembershipRole.ADMIN,
        "a0000000-0000-4000-8000-000000000002": MembershipRole.TUTOR,
        "a0000000-0000-4000-8000-000000000003": MembershipRole.STUDENT,
        "a0000000-0000-4000-8000-000000000004": MembershipRole.STUDENT,
    }

    for subject, expected_role in expected_roles.items():
        user = find_active_user_by_subject(subject)

        assert user is not None
        assert len(user.memberships) == 1
        assert user.memberships[0].role is expected_role
        assert str(user.memberships[0].organization_id) == ORGANIZATION_ID
        assert user.roles_for(user.memberships[0].organization_id) == {
            expected_role
        }


@requires_database
@requires_seed_tests
def test_unknown_cognito_subject_has_no_database_identity() -> None:
    """Reject a valid external identity without a SkillPulse user record."""

    load_synthetic_data()

    assert find_active_user_by_subject("unknown-cognito-subject") is None
