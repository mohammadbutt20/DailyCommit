from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.models import TestCase


async def tests_for_run(db: AsyncSession, problem_id: int, kind: str) -> Sequence[TestCase]:
    """The ordered tests a submission runs: samples first, then hidden ones (submit only).
    A result's ordinal is its index in this list, shared by the worker and the API."""
    query = select(TestCase).where(TestCase.problem_id == problem_id)
    if kind == "run":
        query = query.where(TestCase.is_sample.is_(True))
    return (await db.scalars(query.order_by(TestCase.is_sample.desc(), TestCase.ordinal))).all()
