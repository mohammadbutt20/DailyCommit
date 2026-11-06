"""A submission's lifecycle after it's queued: writing its result, and recovering it when the
job that should have judged it is lost.

The rule that keeps retries, late jobs and the stale sweep from contradicting each other:

- A submission is *final* once it's `done` with a real verdict (anything but IE).
- IE is provisional. It means "we have no real result", whether from the sweep or from a job
  that failed internally on its last try. A later job that gets a real result replaces it.
- The final write locks the row. The first real result wins; any attempt that finishes later
  finds the row final and is discarded (no write, no streak credit, no events).
- Streak credit happens only in that winning write, and `record_solves` inserts at most one
  solve per (group, day, user) anyway.
- The sweep only touches rows still `queued`/`running`, so it can never overwrite a result.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.models import Submission, SubmissionResult
from dailycommit.sandbox.runner import RunReport
from dailycommit.services.events import publish, submission_topic
from dailycommit.services.solves import record_solves

INTERNAL_ERROR = "Internal error, please try again."


def is_final(status: str, verdict: str | None) -> bool:
    return status == "done" and verdict is not None and verdict != "IE"


@dataclass
class Finalized:
    written: bool  # False: another attempt already wrote a real result; this one is discarded
    credited: list[tuple[int, date]] = field(default_factory=list)


async def finalize_submission(
    db: AsyncSession, submission_id: int, report: RunReport, finished: datetime
) -> Finalized:
    """Write `report` as the submission's result unless it's already final. Call inside a
    transaction; the row stays locked until it commits."""
    sub = await db.scalar(
        select(Submission).where(Submission.id == submission_id).with_for_update()
    )
    if sub is None or is_final(sub.status, sub.verdict):
        return Finalized(written=False)
    sub.status = "done"
    sub.verdict = report.verdict
    sub.passed, sub.total = report.passed, report.total
    sub.runtime_ms = report.runtime_ms
    sub.error = report.error
    sub.finished_at = finished
    # Replaces whatever an earlier attempt left (an IE row has none, but be exact).
    await db.execute(delete(SubmissionResult).where(SubmissionResult.submission_id == sub.id))
    db.add_all(
        SubmissionResult(
            submission_id=sub.id,
            ordinal=r.ordinal,
            verdict=r.verdict,
            time_ms=r.time_ms,
            actual=r.actual,
            stdout=r.stdout,
            error=r.error,
        )
        for r in report.results
    )
    credited: list[tuple[int, date]] = []
    if sub.kind == "submit" and report.verdict == "AC":
        credited = await record_solves(
            db, sub.user_id, sub.problem_id, finished, submission_id=sub.id
        )
    return Finalized(written=True, credited=credited)


async def fail_stale_submissions(
    db: AsyncSession, redis: Redis, now: datetime, stale_after_s: int
) -> list[int]:
    """Mark submissions stuck in queued/running for longer than any job could take as IE, and
    tell their browsers. Safe to run any time: a job that still finishes later replaces the IE
    with its real result (see the module docstring)."""
    cutoff = now - timedelta(seconds=stale_after_s)
    async with db.begin():
        rows = (
            await db.execute(
                update(Submission)
                .where(Submission.status.in_(("queued", "running")), Submission.created_at < cutoff)
                .values(status="done", verdict="IE", error=INTERNAL_ERROR, finished_at=now)
                .returning(Submission.id, Submission.total)
            )
        ).all()
    for submission_id, total in rows:
        await publish(
            redis,
            submission_topic(submission_id),
            "final",
            {"verdict": "IE", "passed": 0, "total": total, "runtime_ms": None},
        )
    return [submission_id for submission_id, _ in rows]
