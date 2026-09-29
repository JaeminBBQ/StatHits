"""App settings, read from the environment and a local `.env` file."""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration, with env-var overrides (case-insensitive field names)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "didyouhit.gg"
    riot_api_key: SecretStr | None = None
    database_url: str = "sqlite:///./data/didyouhit.db"
    week_tz: str = "America/Los_Angeles"
    invite_code: str | None = None
    poll_interval_min: int = 15
    min_game_duration_s: int = 300
    rate_limits: str = "20:1,100:120"
    backfill_days: int = 7
    ingest_enabled: bool = False
    alert_webhook_url: SecretStr | None = None
    display_limit: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
