from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    app_name: str = "SkillPulse API"
    app_version: str = "0.1.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    api_prefix: str = "/api/v1"
    cognito_region: str | None = None
    cognito_user_pool_id: str | None = None
    cognito_app_client_id: str | None = None
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    postgres_db: str = "skillpulse"
    postgres_user: str = "skillpulse"
    postgres_password: SecretStr = SecretStr("skillpulse_local_only")
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=55432, ge=1, le=65535)
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    def validated_cognito_configuration(self) -> tuple[str, str, str]:
        """Return required Cognito settings or fail closed."""

        if (
            not self.cognito_region
            or not self.cognito_user_pool_id
            or not self.cognito_app_client_id
        ):
            raise ValueError("Cognito authentication settings are incomplete.")

        return (
            self.cognito_region,
            self.cognito_user_pool_id,
            self.cognito_app_client_id,
        )

    @property
    def cognito_issuer(self) -> str:
        """Return the trusted Cognito user-pool issuer."""

        region, user_pool_id, _ = self.validated_cognito_configuration()
        return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"

    @property
    def cognito_jwks_url(self) -> str:
        """Return the Cognito JSON Web Key Set endpoint."""

        return f"{self.cognito_issuer}/.well-known/jwks.json"


    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
