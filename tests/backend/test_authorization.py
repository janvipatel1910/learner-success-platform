from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    get_current_user,
    require_organization_roles,
)
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000099")


def build_user(*roles: MembershipRole) -> AuthenticatedUser:
    """Create a user with controlled roles in the demonstration organisation."""

    memberships = tuple(
        OrganizationMembership(
            organization_id=ORGANIZATION_ID,
            organization_name="SkillPulse Demo Academy",
            organization_slug="skillpulse-demo-academy",
            role=role,
        )
        for role in roles
    )

    return AuthenticatedUser(
        user_id=UUID("20000000-0000-0000-0000-000000000002"),
        email="authorized.user@skillpulse.example",
        full_name="Authorized User",
        memberships=memberships,
    )


def create_role_test_application(user: AuthenticatedUser) -> FastAPI:
    """Create an isolated route protected for tutors and administrators."""

    application = FastAPI()
    teaching_access = require_organization_roles(
        MembershipRole.TUTOR,
        MembershipRole.ADMIN,
    )

    @application.get("/protected-teaching-area")
    def read_protected_teaching_area(
        access: Annotated[
            OrganizationAccess,
            Depends(teaching_access),
        ],
    ) -> dict[str, str | list[str]]:
        return {
            "organization_id": str(access.organization_id),
            "roles": sorted(role.value for role in access.roles),
        }

    application.dependency_overrides[get_current_user] = lambda: user
    return application


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.TUTOR,
        MembershipRole.ADMIN,
    ],
)
def test_tutor_and_admin_can_access_teaching_area(
    role: MembershipRole,
) -> None:
    application = create_role_test_application(build_user(role))

    with TestClient(application) as client:
        response = client.get(
            "/protected-teaching-area",
            headers={"X-Organization-ID": str(ORGANIZATION_ID)},
        )

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": str(ORGANIZATION_ID),
        "roles": [role.value],
    }


def test_student_cannot_access_teaching_area() -> None:
    application = create_role_test_application(
        build_user(MembershipRole.STUDENT)
    )

    with TestClient(application) as client:
        response = client.get(
            "/protected-teaching-area",
            headers={"X-Organization-ID": str(ORGANIZATION_ID)},
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient organization permissions."
    }


def test_user_cannot_access_unrelated_organization() -> None:
    application = create_role_test_application(
        build_user(MembershipRole.ADMIN)
    )

    with TestClient(application) as client:
        response = client.get(
            "/protected-teaching-area",
            headers={"X-Organization-ID": str(OTHER_ORGANIZATION_ID)},
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient organization permissions."
    }


def test_organization_header_is_required() -> None:
    application = create_role_test_application(
        build_user(MembershipRole.ADMIN)
    )

    with TestClient(application) as client:
        response = client.get("/protected-teaching-area")

    assert response.status_code == 422


def test_role_guard_requires_at_least_one_allowed_role() -> None:
    with pytest.raises(
        ValueError,
        match="At least one organization role is required.",
    ):
        require_organization_roles()
