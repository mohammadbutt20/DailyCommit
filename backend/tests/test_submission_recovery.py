"""Retries, late jobs and the stale-submission sweep, against a real PostgreSQL.

They run in a throwaway database (`<name>_test`, rebuilt with the Alembic migrations) and are
skipped when no PostgreSQL is reachable (e.g. `uv run pytest` outside Docker). Submissions are
judged for real with the Python harness via LocalProcessSandbox.
"""

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
from arq import Retry
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from dailycommit.config import settings
from dailycommit.jobs import worker
from dailycommit.models import (
    Group,
    GroupDailyProblem,
    GroupDaySolve,
    GroupMember,
    Problem,
    Submission,
    SubmissionResult,
    TestCase,
    User,
)
from dailycommit.sandbox.runner import RunReport
from dailycommit.services.submissions import (
    INTERNAL_ERROR,
    fail_stale_submissions,
    finalize_submission,
)
from tests.conftest import LocalProcessSandbox

BACKEND = Path(__file__).resolve().parents[1]
MAIN_URL = make_url(settings.database_url)
TEST_URL = MAIN_URL.set(database=f"{MAIN_URL.database}_test")
AC_CODE = "class Solution:\n    def add(self, a, b):\n        return a + b\n"
WA_CODE = "class Solution:\n    def add(self, a, b):\n        return 0\n"
STALE_AFTER_S = 600


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


@pytest.fixture(scope="module")
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
        import json

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


class BrokenSandbox:
    def run(self, req, on_line):
        raise RuntimeError("docker daemon went away")


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
                            "group_day_solves submission_results submissions group_daily_problems "
                            "test_cases group_members groups problems users"
                        ).split()
                    )
                    await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
                return await scenario(factory)
            finally:
                await engine.dispose()

        return asyncio.run(go())

    return run


async def seed(factory, *, code=AC_CODE, status="running", age=timedelta(hours=1)) -> int:
    """A member of a group whose problem today is `add`, with one submit for it."""
    now = datetime.now(UTC)
    async with factory() as s, s.begin():
        user = User(display_name="Ann")
        s.add(user)
        await s.flush()
        group = Group(
            name="g",
            invite_code="RECOVER1",
            timezone="UTC",
            created_by=user.id,
            last_rolled_day=now.date() - timedelta(days=1),
        )
        problem = Problem(
            slug="add",
            title="Add",
            difficulty="easy",
            topics=["math"],
            statement_md="",
            content_hash="x",
            signature={
                "function": "add",
                "params": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
                "returns": "int",
            },
            compare="exact",
            limits={"time_ms": 1000, "memory_mb": 64},
        )
        s.add_all([group, problem])
        await s.flush()
        s.add_all(
            [
                GroupMember(
                    group_id=group.id,
                    user_id=user.id,
                    role="leader",
                    joined_at=now - timedelta(days=2),
                ),
                TestCase(
                    problem_id=problem.id,
                    ordinal=0,
                    is_sample=True,
                    input={"a": 1, "b": 2},
                    expected=3,
                ),
                TestCase(
                    problem_id=problem.id,
                    ordinal=1,
                    is_sample=False,
                    input={"a": 5, "b": 5},
                    expected=10,
                ),
                GroupDailyProblem(group_id=group.id, day=now.date(), problem_id=problem.id),
            ]
        )
        sub = Submission(
            user_id=user.id,
            problem_id=problem.id,
            language="python",
            kind="submit",
            code=code,
            status=status,
            created_at=now - age,
        )
        s.add(sub)
        await s.flush()
        return sub.id


async def state(factory, submission_id):
    async with factory() as s:
        sub = await s.get(Submission, submission_id)
        results = await s.scalar(
            select(func.count()).where(SubmissionResult.submission_id == submission_id)
        )
        solves = await s.scalar(select(func.count()).select_from(GroupDaySolve))
        return sub.status, sub.verdict, sub.passed, sub.total, results, solves


def ctx(redis, sandbox=None, job_try=1):
    return {"redis": redis, "sandbox": sandbox or LocalProcessSandbox(), "job_try": job_try}


def test_late_ac_after_the_sweep_wins(db):
    async def scenario(factory):
        sid = await seed(factory)
        redis = FakeRedis()
        async with factory() as s:
            assert await fail_stale_submissions(s, redis, datetime.now(UTC), STALE_AFTER_S) == [sid]
        assert (await state(factory, sid))[:2] == ("done", "IE")

        # The job that was thought lost finishes after all.
        assert await worker.run_submission(ctx(redis), sid) == "AC"
        assert await state(factory, sid) == ("done", "AC", 2, 2, 2, 1)
        # The browser saw IE, then the real result last.
        assert redis.finals(sid) == ["IE", "AC"]
        assert redis.solve_events() == 1

    db(scenario)


def test_retry_after_the_sweep_runs_instead_of_skipping(db):
    async def scenario(factory):
        sid = await seed(factory, code=WA_CODE, status="queued")  # its job was lost
        redis = FakeRedis()
        async with factory() as s:
            await fail_stale_submissions(s, redis, datetime.now(UTC), STALE_AFTER_S)
        assert await worker.run_submission(ctx(redis, job_try=2), sid) == "WA"
        status, verdict, passed, total, results, solves = await state(factory, sid)
        assert (status, verdict, passed, total, solves) == ("done", "WA", 0, 2, 0)
        assert redis.finals(sid) == ["IE", "WA"]

    db(scenario)


def test_two_jobs_racing_record_one_result_and_one_solve(db):
    async def scenario(factory):
        sid = await seed(factory)
        redis = FakeRedis()
        outcomes = await asyncio.gather(
            worker.run_submission(ctx(redis), sid),
            worker.run_submission(ctx(redis, job_try=2), sid),
        )
        assert sorted(outcomes) == ["AC", "superseded"]
        assert await state(factory, sid) == ("done", "AC", 2, 2, 2, 1)
        assert redis.finals(sid) == ["AC"] and redis.solve_events() == 1
        # And a third, later attempt doesn't even run.
        assert await worker.run_submission(ctx(redis), sid) == "skipped"

    db(scenario)


def test_a_real_result_is_never_replaced(db):
    async def scenario(factory):
        sid = await seed(factory)
        redis = FakeRedis()
        assert await worker.run_submission(ctx(redis), sid) == "AC"
        late_ie = RunReport("IE", 0, 2, None, INTERNAL_ERROR)
        async with factory() as s, s.begin():
            assert not (await finalize_submission(s, sid, late_ie, datetime.now(UTC))).written
        async with factory() as s:  # the sweep leaves done rows alone, however old
            assert (
                await fail_stale_submissions(s, redis, datetime.now(UTC) + timedelta(days=1), 1)
                == []
            )
        assert (await state(factory, sid))[:2] == ("done", "AC")

    db(scenario)


def test_sweep_only_touches_stale_unfinished_rows(db):
    async def scenario(factory):
        stale = await seed(factory, status="queued")
        async with factory() as s, s.begin():
            fresh = Submission(
                user_id=1, problem_id=1, language="python", kind="run", code="x", status="running"
            )
            s.add(fresh)
        redis = FakeRedis()
        async with factory() as s:
            assert await fail_stale_submissions(s, redis, datetime.now(UTC), STALE_AFTER_S) == [
                stale
            ]
        assert (await state(factory, fresh.id))[:2] == ("running", None)

    db(scenario)


def test_internal_error_retries_once_then_is_ie(db):
    async def scenario(factory):
        sid = await seed(factory, age=timedelta(0))
        redis = FakeRedis()
        with pytest.raises(Retry):
            await worker.run_submission(ctx(redis, BrokenSandbox(), job_try=1), sid)
        assert (await state(factory, sid))[:2] == ("running", None)  # still pending for the retry
        assert await worker.run_submission(ctx(redis, BrokenSandbox(), job_try=2), sid) == "IE"
        assert (await state(factory, sid))[:2] == ("done", "IE")
        # IE is provisional: a job that later gets a real result replaces it.
        assert await worker.run_submission(ctx(redis), sid) == "AC"
        assert await state(factory, sid) == ("done", "AC", 2, 2, 2, 1)

    db(scenario)
