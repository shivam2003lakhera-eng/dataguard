from functools import lru_cache
from pathlib import Path

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
    data_input_dir: Path = Path("sample_data")
    max_file_size_mb: int = Field(default=50, gt=0)
    api_timeout_seconds: float = Field(default=10.0, gt=0)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings object (created on first use)."""
    return Settings()