from datetime import date, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.domain.activity import solve_id
from dailycommit.models import Group, GroupDailyProblem, GroupDaySolve, GroupMember
from dailycommit.services import leaderboard
from dailycommit.services.clock import today
from dailycommit.services.events import group_topic, publish


async def record_solves(
    db: AsyncSession,
    user_id: int,
    problem_id: int,
    solved_at: datetime,
    *,
    submission_id: int | None = None,
    external_ref: str | None = None,
) -> list[tuple[int, date]]:
    """Credit an accepted solve to every group of the user whose problem for that group's
    local day (at `solved_at`) matches. Exactly one of submission_id (our judge) or
    external_ref (a LeetCode submission id) identifies the solve.

    Days the rollover has already evaluated are never credited: a solve found late (e.g. a
    LeetCode accept seen after midnight) must not contradict the recorded streak outcome.
    Returns (group_id, day) for each group where this is the user's first solve of that day.
    """
    assert (submission_id is None) != (external_ref is None)
    groups = (
        await db.scalars(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == user_id)
        )
    ).all()
    credited = []
    for group in groups:
        day = today(group, solved_at)
        if day <= group.last_rolled_day:
            continue
        assigned = await db.scalar(
            select(GroupDailyProblem.problem_id).where(
                GroupDailyProblem.group_id == group.id, GroupDailyProblem.day == day
            )
        )
        if assigned != problem_id:
            continue
        result = await db.execute(
            insert(GroupDaySolve)
            .values(
                group_id=group.id,
                day=day,
                user_id=user_id,
                submission_id=submission_id,
                external_ref=external_ref,
                solved_at=solved_at,
            )
            .on_conflict_do_nothing()
            .returning(GroupDaySolve.group_id)
        )
        if result.scalar() is not None:
            credited.append((group.id, day))
    return credited


async def announce_solves(
    redis: Redis,
    credited: list[tuple[int, date]],
    *,
    user_id: int,
    display_name: str,
    problem_slug: str,
    solved_at: datetime,
) -> None:
    """After the commit: refresh leaderboards and tell each group's live feed."""
    for group_id, day in credited:
        await leaderboard.invalidate(redis, group_id, day)
        await publish(
            redis,
            group_topic(group_id),
            "solve",
            {
                "id": solve_id(day, user_id),  # same id as in GET /groups/{id}/activity
                "user_id": user_id,
                "display_name": display_name,
                "problem": problem_slug,
                "at": solved_at.isoformat(),
            },
        )
