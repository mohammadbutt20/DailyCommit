from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.models import GroupDailyProblem, GroupDaySolve, GroupMember
from dailycommit.services.clock import today


async def record_solves(
    db: AsyncSession, user_id: int, problem_id: int, submission_id: int, solved_at: datetime
) -> list[int]:
    """Credit an accepted submit to every group of the user whose problem for that day matches.
    Returns the ids of groups where this is the user's first solve of the day."""
    # Single app-wide timezone, so "that day" is the same for every group. With per-group
    # timezones this becomes a per-group lookup.
    day = today(now=solved_at)
    group_ids = (
        await db.scalars(
            select(GroupDailyProblem.group_id)
            .join(
                GroupMember,
                (GroupMember.group_id == GroupDailyProblem.group_id)
                & (GroupMember.user_id == user_id),
            )
            .where(GroupDailyProblem.problem_id == problem_id, GroupDailyProblem.day == day)
        )
    ).all()
    credited = []
    for group_id in group_ids:
        result = await db.execute(
            insert(GroupDaySolve)
            .values(
                group_id=group_id,
                day=day,
                user_id=user_id,
                submission_id=submission_id,
                solved_at=solved_at,
            )
            .on_conflict_do_nothing()
            .returning(GroupDaySolve.group_id)
        )
        if result.scalar() is not None:
            credited.append(group_id)
    return credited
