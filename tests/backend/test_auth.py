from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies import auth as auth_dependencies
from skillpulse.core.security import (
    AuthenticationConfigurationError,
    TokenVerificationError,
)
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)


class StubTokenVerifier:
    """Return controlled claims or an authentication error."""

    def __init__(
        self,
        claims: dict[str, str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.claims = claims
        self.error = error

    def verify(self, _: str) -> dict[str, str]:
        if self.error is not None:
            raise self.error

        assert self.claims is not None
        return self.claims


def build_active_user() -> AuthenticatedUser:
    """Create an active synthetic learner identity."""

    return AuthenticatedUser(
        user_id=UUID("20000000-0000-0000-0000-000000000003"),
        email="learner.one@skillpulse.example",
        full_name="Demo Learner One",
        memberships=(
            OrganizationMembership(
                organization_id=UUID(
                    "10000000-0000-0000-0000-000000000001"
                ),
                organization_name="SkillPulse Demo Academy",
                organization_slug="skillpulse-demo-academy",
                role=MembershipRole.STUDENT,
            ),
        ),
    )


def test_current_user_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "detail": "Authentication credentials are invalid."
    }


def test_current_user_rejects_invalid_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = StubTokenVerifier(
        error=TokenVerificationError("Invalid access token.")
    )
    monkeypatch.setattr(
        auth_dependencies,
        "get_token_verifier",
        lambda: verifier,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer untrusted-token"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication credentials are invalid."
    }


def test_current_user_returns_active_database_identity(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = StubTokenVerifier(claims={"sub": "trusted-subject"})
    user = build_active_user()

    monkeypatch.setattr(
        auth_dependencies,
        "get_token_verifier",
        lambda: verifier,
    )
    monkeypatch.setattr(
        auth_dependencies,
        "find_active_user_by_subject",
        lambda _: user,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer trusted-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "20000000-0000-0000-0000-000000000003",
        "email": "learner.one@skillpulse.example",
        "full_name": "Demo Learner One",
        "memberships": [
            {
                "organization_id": (
                    "10000000-0000-0000-0000-000000000001"
                ),
                "organization_name": "SkillPulse Demo Academy",
                "organization_slug": "skillpulse-demo-academy",
                "role": "student",
            }
        ],
    }


def test_current_user_rejects_unregistered_subject(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = StubTokenVerifier(claims={"sub": "unknown-subject"})

    monkeypatch.setattr(
        auth_dependencies,
        "get_token_verifier",
        lambda: verifier,
    )
    monkeypatch.setattr(
        auth_dependencies,
        "find_active_user_by_subject",
        lambda _: None,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer trusted-token"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authenticated user is not authorized."
    }


def test_current_user_fails_closed_when_authentication_is_unconfigured(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_verifier() -> StubTokenVerifier:
        raise AuthenticationConfigurationError(
            "Authentication is not configured."
        )

    monkeypatch.setattr(
        auth_dependencies,
        "get_token_verifier",
        unavailable_verifier,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer any-token"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Authentication service is unavailable."
    }


def test_current_user_hides_database_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = StubTokenVerifier(claims={"sub": "trusted-subject"})

    def unavailable_database(_: str) -> AuthenticatedUser | None:
        raise SQLAlchemyError("Sensitive database failure")

    monkeypatch.setattr(
        auth_dependencies,
        "get_token_verifier",
        lambda: verifier,
    )
    monkeypatch.setattr(
        auth_dependencies,
        "find_active_user_by_subject",
        unavailable_database,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer trusted-token"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Identity service is unavailable."
    }
def test_openapi_documents_cognito_bearer_security(
    client: TestClient,
) -> None:
    schema = client.get("/openapi.json").json()

    route_security = schema["paths"]["/api/v1/auth/me"]["get"]["security"]
    security_scheme = schema["components"]["securitySchemes"][
        "CognitoAccessToken"
    ]

    assert route_security == [{"CognitoAccessToken": []}]
    assert security_scheme == {
        "type": "http",
        "description": "Amazon Cognito access token",
        "scheme": "bearer",
    }
