"""Scheduler: `arq dailycommit.jobs.scheduler.SchedulerSettings`. Run exactly one replica."""

import logging
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from dailycommit.config import settings
from dailycommit.db import SessionLocal
from dailycommit.models import utcnow
from dailycommit.services.rollover import rollover_all

log = logging.getLogger(__name__)


async def rollover(ctx: dict[str, Any]) -> int:
    async with SessionLocal() as db:
        count = await rollover_all(db, utcnow())
    log.info("rolled over %d groups", count)
    return count


class SchedulerSettings:
    queue_name = "arq:scheduler"  # separate from the submission queue
    functions = [rollover]
    cron_jobs = [cron(rollover, minute=set(range(0, 60, 5)), run_at_startup=True)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
