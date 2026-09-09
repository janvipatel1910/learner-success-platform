import pytest
from pydantic import ValidationError

from skillpulse.core.config import Settings


def test_database_url_uses_typed_postgres_settings() -> None:
    settings = Settings(
        postgres_db="skillpulse_test",
        postgres_user="test_user",
        postgres_password="test_password",
        postgres_host="database",
        postgres_port=5432,
    )

    database_url = settings.database_url

    assert database_url.drivername == "postgresql+psycopg"
    assert database_url.database == "skillpulse_test"
    assert database_url.username == "test_user"
    assert database_url.password == "test_password"
    assert database_url.host == "database"
    assert database_url.port == 5432
    assert "test_password" not in str(database_url)


def test_settings_load_database_values_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_DB", "environment_db")
    monkeypatch.setenv("POSTGRES_USER", "environment_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "environment_password")
    monkeypatch.setenv("POSTGRES_PORT", "6543")

    settings = Settings(_env_file=None)

    assert settings.postgres_db == "environment_db"
    assert settings.postgres_user == "environment_user"
    assert settings.postgres_password.get_secret_value() == (
        "environment_password"
    )
    assert settings.postgres_port == 6543


def test_invalid_database_port_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(postgres_port=70000)
def test_cognito_urls_are_derived_from_validated_settings() -> None:
    settings = Settings(
        _env_file=None,
        cognito_region="eu-west-2",
        cognito_user_pool_id="eu-west-2_example",
        cognito_app_client_id="example-client-id",
    )

    assert settings.validated_cognito_configuration() == (
        "eu-west-2",
        "eu-west-2_example",
        "example-client-id",
    )
    assert settings.cognito_issuer == (
        "https://cognito-idp.eu-west-2.amazonaws.com/eu-west-2_example"
    )
    assert settings.cognito_jwks_url == (
        "https://cognito-idp.eu-west-2.amazonaws.com/"
        "eu-west-2_example/.well-known/jwks.json"
    )


def test_incomplete_cognito_configuration_fails_closed() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(
        ValueError,
        match="Cognito authentication settings are incomplete",
    ):
        settings.validated_cognito_configuration()


def test_invalid_jwt_clock_skew_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_clock_skew_seconds=301)
def test_empty_cognito_configuration_is_rejected() -> None:
    settings = Settings(
        cognito_region="",
        cognito_user_pool_id="",
        cognito_app_client_id="",
        _env_file=None,
    )

    with pytest.raises(
        ValueError,
        match="Cognito authentication settings are incomplete.",
    ):
        settings.validated_cognito_configuration()
