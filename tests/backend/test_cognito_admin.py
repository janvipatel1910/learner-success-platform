from typing import Any

import pytest
from botocore.exceptions import ClientError

from skillpulse.core import cognito_admin
from skillpulse.core.config import Settings


class StubCognitoClient:
    """A fake Cognito client that records calls instead of calling AWS."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def admin_create_user(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("admin_create_user", kwargs))
        if self.error is not None:
            raise self.error
        return {
            "User": {
                "Attributes": [
                    {"Name": "email", "Value": kwargs["Username"]},
                    {"Name": "sub", "Value": "new-cognito-subject"},
                ]
            }
        }

    def admin_delete_user(self, **kwargs: Any) -> None:
        self.calls.append(("admin_delete_user", kwargs))
        if self.error is not None:
            raise self.error


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "AdminCreateUser")


@pytest.fixture
def stub_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        cognito_region="eu-west-2",
        cognito_user_pool_id="eu-west-2_TestPool",
        cognito_app_client_id="test-client",
    )
    monkeypatch.setattr(cognito_admin, "get_settings", lambda: settings)


def test_invite_creates_user_and_returns_subject(
    monkeypatch: pytest.MonkeyPatch,
    stub_settings: None,
) -> None:
    client = StubCognitoClient()
    monkeypatch.setattr(cognito_admin, "get_cognito_client", lambda: client)

    subject = cognito_admin.invite_cognito_user(
        email="new.learner@example.com",
        full_name="New Learner",
    )

    assert subject == "new-cognito-subject"
    name, kwargs = client.calls[0]
    assert name == "admin_create_user"
    assert kwargs["UserPoolId"] == "eu-west-2_TestPool"
    assert kwargs["Username"] == "new.learner@example.com"
    assert kwargs["DesiredDeliveryMediums"] == ["EMAIL"]
    assert {"Name": "email_verified", "Value": "true"} in kwargs["UserAttributes"]


def test_invite_reports_existing_cognito_user(
    monkeypatch: pytest.MonkeyPatch,
    stub_settings: None,
) -> None:
    client = StubCognitoClient(error=_client_error("UsernameExistsException"))
    monkeypatch.setattr(cognito_admin, "get_cognito_client", lambda: client)

    with pytest.raises(cognito_admin.CognitoUserExistsError):
        cognito_admin.invite_cognito_user(
            email="existing@example.com",
            full_name="Existing User",
        )


def test_invite_wraps_other_cognito_errors(
    monkeypatch: pytest.MonkeyPatch,
    stub_settings: None,
) -> None:
    client = StubCognitoClient(error=_client_error("AccessDeniedException"))
    monkeypatch.setattr(cognito_admin, "get_cognito_client", lambda: client)

    with pytest.raises(cognito_admin.CognitoAdminError):
        cognito_admin.invite_cognito_user(
            email="new.learner@example.com",
            full_name="New Learner",
        )


def test_delete_removes_cognito_user(
    monkeypatch: pytest.MonkeyPatch,
    stub_settings: None,
) -> None:
    client = StubCognitoClient()
    monkeypatch.setattr(cognito_admin, "get_cognito_client", lambda: client)

    cognito_admin.delete_cognito_user("new.learner@example.com")

    assert client.calls == [
        (
            "admin_delete_user",
            {
                "UserPoolId": "eu-west-2_TestPool",
                "Username": "new.learner@example.com",
            },
        )
    ]
