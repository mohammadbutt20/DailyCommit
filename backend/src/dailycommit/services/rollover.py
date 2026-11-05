"""The daily rollover: evaluate finished days' streaks and make sure today has a problem.

Idempotent: safe to run every few minutes, twice, or after downtime (it catches up day by day).
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.domain import streaks, timeutil
from dailycommit.models import Group, GroupDaySolve, GroupMember, GroupStreakDay
from dailycommit.services.clock import group_tz, today
from dailycommit.services.daily import ensure_daily_problem


async def rollover_group(db: AsyncSession, group_id: int, now: datetime) -> None:
    group = await db.scalar(select(Group).where(Group.id == group_id).with_for_update())
    if group is None:
        return
    tz = group_tz(group.id)
    current_day = today(group.id, now)
    members = [
        streaks.Member(m.user_id, m.joined_at, m.paused)
        for m in (
            await db.scalars(select(GroupMember).where(GroupMember.group_id == group.id))
        ).all()
    ]
    streak = streaks.Streak(group.current_streak, group.best_streak)

    for day in timeutil.days_between(
        group.last_rolled_day + timedelta(days=1), current_day - timedelta(days=1)
    ):
        solved = (
            await db.scalars(
                select(GroupDaySolve.user_id).where(
                    GroupDaySolve.group_id == group.id, GroupDaySolve.day == day
                )
            )
        ).all()
        outcome = streaks.evaluate_day(members, solved, timeutil.day_start(day, tz))
        streak = streaks.apply_outcome(streak, outcome)
        await db.execute(
            insert(GroupStreakDay)
            .values(
                group_id=group.id,
                day=day,
                eligible_count=outcome.eligible_count,
                solved_count=outcome.solved_count,
                kept=outcome.kept,
            )
            .on_conflict_do_nothing()
        )
        group.last_rolled_day = day
        # P1 hooks: unlock solutions for `day`, post the Discord summary.

    group.current_streak, group.best_streak = streak.current, streak.best
    await ensure_daily_problem(db, group.id, current_day)


async def rollover_all(db: AsyncSession, now: datetime) -> int:
    group_ids = (await db.scalars(select(Group.id))).all()
    await db.commit()  # end the autobegun read so each group gets its own transaction
    for group_id in group_ids:
        async with db.begin():
            await rollover_group(db, group_id, now)
    return len(group_ids)
