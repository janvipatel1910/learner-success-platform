from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import invitations as invitation_routes
from skillpulse.core.cognito_admin import CognitoAdminError, CognitoUserExistsError
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)
from skillpulse.db.invitations import CreatedInvitation, UserAlreadyExistsError

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
NEW_USER_ID = UUID("20000000-0000-0000-0000-000000000099")
NEW_MEMBERSHIP_ID = UUID("30000000-0000-0000-0000-000000000099")
INVITATIONS_PATH = "/api/v1/admin/invitations"
HEADERS = {"X-Organization-ID": str(ORGANIZATION_ID)}


def build_user(role: MembershipRole) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=UUID("20000000-0000-0000-0000-000000000001"),
        email="current.user@skillpulse.example",
        full_name="Current User",
        memberships=(
            OrganizationMembership(
                organization_id=ORGANIZATION_ID,
                organization_name="SkillPulse Demo Academy",
                organization_slug="skillpulse-demo-academy",
                role=role,
            ),
        ),
    )


def create_client(role: MembershipRole) -> TestClient:
    application = FastAPI()
    application.include_router(invitation_routes.router, prefix="/api/v1")
    application.dependency_overrides[get_current_user] = lambda: build_user(role)
    return TestClient(application)


def valid_payload() -> dict[str, str]:
    return {
        "email": "  New.Learner@Example.com ",
        "full_name": "New Learner",
        "role": "student",
    }


class FakeServices:
    """Records calls to Cognito and the database instead of using real services."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.invited: list[str] = []
        self.deleted: list[str] = []
        self.saved: list[dict[str, object]] = []
        self.cognito_error: Exception | None = None
        self.database_error: Exception | None = None

        def invite(*, email: str, full_name: str) -> str:
            if self.cognito_error is not None:
                raise self.cognito_error
            self.invited.append(email)
            return "new-cognito-subject"

        def save(**kwargs: object) -> CreatedInvitation:
            if self.database_error is not None:
                raise self.database_error
            self.saved.append(kwargs)
            return CreatedInvitation(user_id=NEW_USER_ID, membership_id=NEW_MEMBERSHIP_ID)

        monkeypatch.setattr(invitation_routes, "invite_cognito_user", invite)
        monkeypatch.setattr(invitation_routes, "create_invitation", save)
        monkeypatch.setattr(invitation_routes, "delete_cognito_user", self.deleted.append)


@pytest.fixture
def services(monkeypatch: pytest.MonkeyPatch) -> FakeServices:
    return FakeServices(monkeypatch)


def test_admin_can_invite_a_learner(services: FakeServices) -> None:
    client = create_client(MembershipRole.ADMIN)

    response = client.post(INVITATIONS_PATH, json=valid_payload(), headers=HEADERS)

    assert response.status_code == 201
    assert response.json() == {
        "user_id": str(NEW_USER_ID),
        "membership_id": str(NEW_MEMBERSHIP_ID),
        "email": "new.learner@example.com",
        "full_name": "New Learner",
        "role": "student",
        "status": "invited",
    }
    assert services.invited == ["new.learner@example.com"]
    assert services.saved[0]["organization_id"] == ORGANIZATION_ID
    assert services.saved[0]["auth_subject"] == "new-cognito-subject"
    assert services.deleted == []


@pytest.mark.parametrize("role", [MembershipRole.STUDENT, MembershipRole.TUTOR])
def test_non_admins_cannot_invite(services: FakeServices, role: MembershipRole) -> None:
    client = create_client(role)

    response = client.post(INVITATIONS_PATH, json=valid_payload(), headers=HEADERS)

    assert response.status_code == 403
    assert services.invited == []


def test_invalid_email_is_rejected(services: FakeServices) -> None:
    client = create_client(MembershipRole.ADMIN)
    payload = valid_payload() | {"email": "not-an-email"}

    response = client.post(INVITATIONS_PATH, json=payload, headers=HEADERS)

    assert response.status_code == 422
    assert services.invited == []


def test_existing_cognito_user_returns_conflict(services: FakeServices) -> None:
    services.cognito_error = CognitoUserExistsError("new.learner@example.com")
    client = create_client(MembershipRole.ADMIN)

    response = client.post(INVITATIONS_PATH, json=valid_payload(), headers=HEADERS)

    assert response.status_code == 409
    assert services.saved == []
    assert services.deleted == []


def test_cognito_failure_returns_service_unavailable(services: FakeServices) -> None:
    services.cognito_error = CognitoAdminError("AccessDenied")
    client = create_client(MembershipRole.ADMIN)

    response = client.post(INVITATIONS_PATH, json=valid_payload(), headers=HEADERS)

    assert response.status_code == 503
    assert services.saved == []


def test_existing_database_user_undoes_cognito_user(services: FakeServices) -> None:
    services.database_error = UserAlreadyExistsError("new.learner@example.com")
    client = create_client(MembershipRole.ADMIN)

    response = client.post(INVITATIONS_PATH, json=valid_payload(), headers=HEADERS)

    assert response.status_code == 409
    assert services.deleted == ["new.learner@example.com"]


def test_database_failure_undoes_cognito_user(services: FakeServices) -> None:
    services.database_error = OperationalError("INSERT", {}, Exception("down"))
    client = create_client(MembershipRole.ADMIN)

    response = client.post(INVITATIONS_PATH, json=valid_payload(), headers=HEADERS)

    assert response.status_code == 503
    assert services.deleted == ["new.learner@example.com"]
