from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from skillpulse.core.config import Settings
from skillpulse.core.security import (
    AuthenticationConfigurationError,
    CognitoAccessTokenVerifier,
    TokenVerificationError,
)


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        cognito_region="eu-west-2",
        cognito_user_pool_id="eu-west-2_example",
        cognito_app_client_id="example-client-id",
        jwt_clock_skew_seconds=0,
    )


def _valid_claims(settings: Settings) -> dict[str, Any]:
    now = datetime.now(UTC)

    return {
        "client_id": settings.cognito_app_client_id,
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "iss": settings.cognito_issuer,
        "sub": "example-cognito-subject",
        "token_use": "access",
        "username": "demo.learner",
    }


def _encode_token(
    claims: dict[str, Any],
    private_key: rsa.RSAPrivateKey,
) -> str:
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def _configure_signing_key(
    verifier: CognitoAccessTokenVerifier,
    private_key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signing_key = SimpleNamespace(key=private_key.public_key())
    monkeypatch.setattr(
        verifier._jwks_client,
        "get_signing_key_from_jwt",
        lambda _: signing_key,
    )


def test_valid_cognito_access_token_is_accepted(
    private_key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    verifier = CognitoAccessTokenVerifier(settings)
    _configure_signing_key(verifier, private_key, monkeypatch)
    token = _encode_token(_valid_claims(settings), private_key)

    claims = verifier.verify(token)

    assert claims["sub"] == "example-cognito-subject"
    assert claims["token_use"] == "access"


@pytest.mark.parametrize(
    ("claim_name", "invalid_value"),
    [
        ("client_id", "wrong-client"),
        ("iss", "https://issuer.example.invalid"),
        ("token_use", "id"),
    ],
)
def test_invalid_cognito_claim_is_rejected(
    claim_name: str,
    invalid_value: str,
    private_key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    verifier = CognitoAccessTokenVerifier(settings)
    _configure_signing_key(verifier, private_key, monkeypatch)
    claims = _valid_claims(settings)
    claims[claim_name] = invalid_value
    token = _encode_token(claims, private_key)

    with pytest.raises(TokenVerificationError, match="Invalid access token"):
        verifier.verify(token)


def test_expired_access_token_is_rejected(
    private_key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    verifier = CognitoAccessTokenVerifier(settings)
    _configure_signing_key(verifier, private_key, monkeypatch)
    claims = _valid_claims(settings)
    claims["exp"] = datetime.now(UTC) - timedelta(minutes=1)
    token = _encode_token(claims, private_key)

    with pytest.raises(TokenVerificationError, match="Invalid access token"):
        verifier.verify(token)


def test_token_with_untrusted_signature_is_rejected(
    private_key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    verifier = CognitoAccessTokenVerifier(settings)
    _configure_signing_key(verifier, private_key, monkeypatch)
    untrusted_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    token = _encode_token(_valid_claims(settings), untrusted_key)

    with pytest.raises(TokenVerificationError, match="Invalid access token"):
        verifier.verify(token)


def test_missing_cognito_configuration_fails_closed() -> None:
    with pytest.raises(
        AuthenticationConfigurationError,
        match="Authentication is not configured",
    ):
        CognitoAccessTokenVerifier(Settings(_env_file=None))
