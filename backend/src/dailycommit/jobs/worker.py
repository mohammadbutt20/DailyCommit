"""Execution worker: `arq dailycommit.jobs.worker.WorkerSettings`. Scale with more replicas."""

import asyncio
import logging
from typing import Any

from arq.connections import RedisSettings

from dailycommit.config import settings
from dailycommit.db import SessionLocal
from dailycommit.models import Problem, Submission, SubmissionResult, User, utcnow
from dailycommit.problems.schema import Signature
from dailycommit.sandbox.backend import DockerSandbox
from dailycommit.sandbox.languages import LANGUAGES
from dailycommit.sandbox.runner import RunReport, TestInput, run_tests
from dailycommit.services import leaderboard
from dailycommit.services.clock import today
from dailycommit.services.events import group_topic, publish, submission_topic
from dailycommit.services.solves import record_solves
from dailycommit.services.testcases import tests_for_run

log = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    sandbox = DockerSandbox()
    removed = await asyncio.to_thread(sandbox.reap_orphans)
    if removed:
        log.warning("removed %d orphaned sandbox containers", removed)
    ctx["sandbox"] = sandbox


async def run_submission(ctx: dict[str, Any], submission_id: int) -> str:
    redis = ctx["redis"]
    topic = submission_topic(submission_id)

    async with SessionLocal() as db:
        sub = await db.get(Submission, submission_id)
        if sub is None or sub.status == "done":
            return "skipped"
        problem = await db.get(Problem, sub.problem_id)
        assert problem is not None
        cases = await tests_for_run(db, problem.id, sub.kind)
        tests = [TestInput(c.input, c.expected, c.is_sample) for c in cases]
        sub.status, sub.total = "running", len(tests)
        language, code, kind, user_id = sub.language, sub.code, sub.kind, sub.user_id
        signature, compare, limits = Signature(**problem.signature), problem.compare, problem.limits
        await db.commit()
    await publish(redis, topic, "status", {"status": "running", "total": len(tests)})

    # The runner calls on_event from its thread; a single forwarder keeps events in order.
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def forward() -> None:
        while (ev := await queue.get()) is not None:
            await publish(redis, topic, ev["event"], ev["data"])

    forwarder = asyncio.create_task(forward())
    try:
        report = await asyncio.to_thread(
            run_tests,
            ctx["sandbox"],
            LANGUAGES[language],
            code,
            signature,
            tests,
            compare,
            limits,
            lambda ev: loop.call_soon_threadsafe(queue.put_nowait, ev),
        )
    except Exception:
        log.exception("submission %s failed internally", submission_id)
        report = RunReport("IE", 0, len(tests), None, "Internal error, please try again.")
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, None)
        await forwarder

    finished = utcnow()
    async with SessionLocal() as db, db.begin():
        sub = await db.get(Submission, submission_id)
        assert sub is not None
        sub.status = "done"
        sub.verdict = report.verdict
        sub.passed, sub.total = report.passed, report.total
        sub.runtime_ms = report.runtime_ms
        sub.error = report.error
        sub.finished_at = finished
        db.add_all(
            SubmissionResult(
                submission_id=submission_id,
                ordinal=r.ordinal,
                verdict=r.verdict,
                time_ms=r.time_ms,
                actual=r.actual,
                stdout=r.stdout,
                error=r.error,
            )
            for r in report.results
        )
        credited: list[int] = []
        if kind == "submit" and report.verdict == "AC":
            credited = await record_solves(db, user_id, problem.id, submission_id, finished)
        user = await db.get(User, user_id)

    for group_id in credited:
        await leaderboard.invalidate(redis, group_id, today(group_id, finished))
        await publish(
            redis,
            group_topic(group_id),
            "solve",
            {
                "user_id": user_id,
                "display_name": user.display_name if user else "?",
                "problem": problem.slug,
                "at": finished.isoformat(),
            },
        )
    await publish(
        redis,
        topic,
        "final",
        {
            "verdict": report.verdict,
            "passed": report.passed,
            "total": report.total,
            "runtime_ms": report.runtime_ms,
        },
    )
    return report.verdict


class WorkerSettings:
    functions = [run_submission]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.worker_max_jobs
    job_timeout = 180
    max_tries = 1
