"""A throwaway PostgreSQL database for integration tests: `<name>_test`, rebuilt once per run
with the Alembic migrations and truncated before each test. Tests that use the `db` fixture are
skipped when no PostgreSQL is reachable (e.g. `uv run pytest` outside Docker)."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from dailycommit.config import settings
from dailycommit.jobs import worker

BACKEND = Path(__file__).resolve().parents[1]
MAIN_URL = make_url(settings.database_url)
TEST_URL = MAIN_URL.set(database=f"{MAIN_URL.database}_test")


async def _reset_database() -> None:
    conn = await asyncpg.connect(
        user=MAIN_URL.username,
        password=MAIN_URL.password,
        host=MAIN_URL.host,
        port=MAIN_URL.port or 5432,
        database=MAIN_URL.database,
        timeout=3,
    )
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_URL.database}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{TEST_URL.database}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def test_db_url() -> str:
    try:
        asyncio.run(_reset_database())
    except (OSError, asyncpg.PostgresError, TimeoutError) as e:
        pytest.skip(f"no PostgreSQL for integration tests: {e}")
    url = TEST_URL.render_as_string(hide_password=False)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        capture_output=True,
    )
    return url


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, dict]] = []

    async def publish(self, channel, message):
        msg = json.loads(message)
        self.published.append((channel, msg["event"], msg["data"]))

    async def delete(self, *keys):
        return len(keys)

    def finals(self, submission_id: int) -> list[str]:
        return [
            d["verdict"]
            for c, e, d in self.published
            if c == f"submission:{submission_id}" and e == "final"
        ]

    def solve_events(self) -> int:
        return sum(1 for c, e, _ in self.published if c.startswith("group:") and e == "solve")


@pytest.fixture
def db(test_db_url, monkeypatch):
    """A clean schema per test; the worker's sessions go to the test database."""

    def session_factory():
        engine = create_async_engine(test_db_url, pool_size=5)
        return engine, async_sessionmaker(engine, expire_on_commit=False)

    def run(scenario):
        async def go():
            engine, factory = session_factory()
            monkeypatch.setattr(worker, "SessionLocal", factory)
            try:
                async with engine.begin() as conn:
                    tables = ", ".join(
                        t
                        for t in (
                            "group_day_solves group_streak_days submission_results submissions "
                            "group_daily_problems "
                            "test_cases group_members groups problems users"
                        ).split()
                    )
                    await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
                return await scenario(factory)
            finally:
                await engine.dispose()

        return asyncio.run(go())

    return run
