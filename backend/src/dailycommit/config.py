from functools import cached_property
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration, read from environment variables (case-insensitive)."""

    model_config = SettingsConfigDict(extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://dailycommit:dailycommit@postgres:5432/dailycommit"
    redis_url: str = "redis://redis:6379/0"

    # One timezone defines "the day" for every group. Per-group timezones are a later slice;
    # all callers go through `day_tz` so that change stays local.
    day_timezone: str = "America/New_York"

    problems_dir: Path = Path("/problems")

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

    @cached_property
    def day_tz(self) -> ZoneInfo:
        return ZoneInfo(self.day_timezone)


settings = Settings()
