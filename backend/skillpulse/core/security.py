"""Amazon Cognito access-token verification."""

from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from skillpulse.core.config import Settings, get_settings


class AuthenticationConfigurationError(RuntimeError):
    """Raised when trusted authentication settings are unavailable."""


class TokenVerificationError(ValueError):
    """Raised when an access token cannot be trusted."""


class CognitoAccessTokenVerifier:
    """Verify Cognito access-token signatures and required claims."""

    def __init__(self, settings: Settings) -> None:
        try:
            _, _, app_client_id = settings.validated_cognito_configuration()
        except ValueError as exc:
            raise AuthenticationConfigurationError(
                "Authentication is not configured."
            ) from exc

        self._app_client_id = app_client_id
        self._issuer = settings.cognito_issuer
        self._clock_skew_seconds = settings.jwt_clock_skew_seconds
        self._jwks_client = PyJWKClient(settings.cognito_jwks_url)

    def verify(self, token: str) -> dict[str, Any]:
        """Verify a signed Cognito access token and return trusted claims."""

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                leeway=self._clock_skew_seconds,
                options={
                    "require": [
                        "client_id",
                        "exp",
                        "iat",
                        "iss",
                        "sub",
                        "token_use",
                    ],
                    "verify_aud": False,
                },
            )
        except (InvalidTokenError, PyJWKClientError) as exc:
            raise TokenVerificationError("Invalid access token.") from exc

        if claims.get("token_use") != "access":
            raise TokenVerificationError("Invalid access token.")

        if claims.get("client_id") != self._app_client_id:
            raise TokenVerificationError("Invalid access token.")

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise TokenVerificationError("Invalid access token.")

        return claims


@lru_cache(maxsize=1)
def get_token_verifier() -> CognitoAccessTokenVerifier:
    """Return the shared verifier and its cached Cognito key client."""

    return CognitoAccessTokenVerifier(get_settings())
