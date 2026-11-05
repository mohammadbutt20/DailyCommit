from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.domain.daily_pick import Candidate, pick_problem
from dailycommit.models import GroupDailyProblem, Problem


async def daily_problem(db: AsyncSession, group_id: int, day: date) -> Problem | None:
    return await db.scalar(
        select(Problem)
        .join(GroupDailyProblem, GroupDailyProblem.problem_id == Problem.id)
        .where(GroupDailyProblem.group_id == group_id, GroupDailyProblem.day == day)
    )


async def ensure_daily_problem(db: AsyncSession, group_id: int, day: date) -> None:
    """Assign the group's problem for `day` unless one exists (auto-picked or leader-chosen)."""
    exists = await db.scalar(
        select(GroupDailyProblem.problem_id).where(
            GroupDailyProblem.group_id == group_id, GroupDailyProblem.day == day
        )
    )
    if exists is not None:
        return
    problems = (await db.scalars(select(Problem).where(Problem.retired.is_(False)))).all()
    history = (
        await db.execute(
            select(GroupDailyProblem.day, GroupDailyProblem.problem_id).where(
                GroupDailyProblem.group_id == group_id, GroupDailyProblem.day < day
            )
        )
    ).all()
    choice = pick_problem(
        [Candidate(p.id, p.slug, tuple(p.topics)) for p in problems],
        [(d, pid) for d, pid in history],
    )
    if choice is None:
        return  # no problems synced yet; the next rollover tries again
    await db.execute(
        insert(GroupDailyProblem)
        .values(group_id=group_id, day=day, problem_id=choice.problem_id)
        .on_conflict_do_nothing()
    )
