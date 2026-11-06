"""Execution worker: `arq dailycommit.jobs.worker.WorkerSettings`. Scale with more replicas."""

import asyncio
import logging
from typing import Any

from arq import Retry
from arq.connections import RedisSettings

from dailycommit.config import settings
from dailycommit.db import SessionLocal
from dailycommit.models import Problem, Submission, User, utcnow
from dailycommit.problems.schema import Signature
from dailycommit.sandbox.backend import DockerSandbox
from dailycommit.sandbox.languages import LANGUAGES
from dailycommit.sandbox.runner import RunReport, TestInput, judge_submission
from dailycommit.services.events import publish, submission_topic
from dailycommit.services.solves import announce_solves
from dailycommit.services.submissions import INTERNAL_ERROR, finalize_submission, is_final
from dailycommit.services.testcases import tests_for_run

log = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    sandbox = DockerSandbox()
    removed = await asyncio.to_thread(sandbox.reap_orphans)
    if removed:
        log.warning("removed %d orphaned sandbox containers", removed)
    ctx["sandbox"] = sandbox


# One retry: after a worker crash (arq re-runs the job once its in-progress key expires, about
# job_timeout + 10 s later) or after an internal error on the first try. Anything left
# unjudged after that is caught by the scheduler's stale-submission sweep.
MAX_TRIES = 2


async def run_submission(ctx: dict[str, Any], submission_id: int) -> str:
    redis = ctx["redis"]
    topic = submission_topic(submission_id)
    job_try = ctx.get("job_try", 1)

    async with SessionLocal() as db:
        sub = await db.get(Submission, submission_id)
        if sub is None or is_final(sub.status, sub.verdict):
            return "skipped"
        problem = await db.get(Problem, sub.problem_id)
        assert problem is not None
        cases = await tests_for_run(db, problem.id, sub.kind)
        tests = [TestInput(c.input, c.expected, c.is_sample) for c in cases]
        # A row the sweep already marked IE stays IE until a real result replaces it.
        if sub.status != "done":
            sub.status = "running"
        sub.total = len(tests)
        language, code, user_id = sub.language, sub.code, sub.user_id
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
            judge_submission,
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
        log.exception("submission %s failed internally (try %d)", submission_id, job_try)
        if job_try < MAX_TRIES:
            raise Retry(defer=2) from None
        report = RunReport("IE", 0, len(tests), None, INTERNAL_ERROR)
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, None)
        await forwarder

    finished = utcnow()
    async with SessionLocal() as db, db.begin():
        result = await finalize_submission(db, submission_id, report, finished)
        user = await db.get(User, user_id)
    if not result.written:
        return "superseded"  # another attempt already recorded a real result

    await announce_solves(
        redis,
        result.credited,
        user_id=user_id,
        display_name=user.display_name if user else "?",
        problem_slug=problem.slug,
        solved_at=finished,
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
    max_tries = MAX_TRIES
