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
