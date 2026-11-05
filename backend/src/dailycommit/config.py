from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration, read from environment variables (case-insensitive)."""

    model_config = SettingsConfigDict(extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://dailycommit:dailycommit@postgres:5432/dailycommit"
    redis_url: str = "redis://redis:6379/0"

    # Default timezone for new groups (each group stores its own; see services/clock.py).
    day_timezone: str = "America/New_York"

    problems_dir: Path = Path("/problems")

    # Where users reach the app; Discord redirects back to <public_url>/api/auth/discord/callback,
    # which must be listed under the Discord application's OAuth2 redirects.
    public_url: str = "http://localhost:8080"
    # Discord OAuth (discord.com/developers). Login with Discord is enabled only when both are set.
    discord_client_id: str = ""
    discord_client_secret: SecretStr = SecretStr("")

    session_cookie: str = "dc_session"
    session_ttl_days: int = 30
    cookie_secure: bool = False

    max_code_bytes: int = 64_000
    submissions_per_minute: int = 10
    worker_max_jobs: int = 4

    sandbox_runtime: str = "runc"  # "runsc" (gVisor) on the VPS
    sandbox_image_prefix: str = "dailycommit-sandbox-"

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def discord_enabled(self) -> bool:
        return bool(self.discord_client_id and self.discord_client_secret.get_secret_value())


settings = Settings()
