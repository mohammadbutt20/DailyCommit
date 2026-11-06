"""Scheduler: `arq dailycommit.jobs.scheduler.SchedulerSettings`. Run exactly one replica."""

import logging
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from dailycommit.config import settings
from dailycommit.db import SessionLocal
from dailycommit.leetcode.client import new_client
from dailycommit.models import utcnow
from dailycommit.services.leetcode_solves import check_all
from dailycommit.services.rollover import rollover_all
from dailycommit.services.submissions import fail_stale_submissions

log = logging.getLogger(__name__)


async def rollover(ctx: dict[str, Any]) -> int:
    # LeetCode solves first, so an accept just before midnight lands before its day is scored.
    try:
        async with SessionLocal() as db, new_client() as http:
            credited = await check_all(db, ctx["redis"], http)
        if credited:
            log.info("credited %d LeetCode solves", credited)
    except Exception:  # never let LeetCode trouble block the rollover
        log.exception("LeetCode check failed")
    async with SessionLocal() as db:
        count = await rollover_all(db, utcnow())
    log.info("rolled over %d groups", count)
    return count


async def recover_submissions(ctx: dict[str, Any]) -> int:
    """Backstop for submissions whose job was lost (worker crashed twice, Redis lost the job,
    enqueue failed, job timed out): mark them IE so nothing stays queued/running forever."""
    async with SessionLocal() as db:
        ids = await fail_stale_submissions(
            db, ctx["redis"], utcnow(), settings.submission_stale_after_s
        )
    if ids:
        log.warning("marked %d stale submissions as IE: %s", len(ids), ids)
    return len(ids)


class SchedulerSettings:
    queue_name = "arq:scheduler"  # separate from the submission queue
    functions = [rollover, recover_submissions]
    cron_jobs = [
        cron(rollover, minute=set(range(0, 60, 5)), run_at_startup=True),
        cron(recover_submissions, run_at_startup=True),  # every minute
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
