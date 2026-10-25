from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str
    test_database_url: str | None = None
    max_file_size_mb: int = Field(default=50, gt=0)
    log_level: str = "INFO"
    session_days: int = Field(default=7, gt=0)
    cookie_secure: bool = False
    allow_registration: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings object (created on first use)."""
    return Settings()