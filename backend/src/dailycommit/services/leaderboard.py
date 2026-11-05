import json
from datetime import date, timedelta
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.domain import leaderboard, timeutil
from dailycommit.models import GroupDaySolve, User
from dailycommit.services.clock import group_tz

Period = Literal["day", "week"]
CACHE_TTL_S = 300


def _anchor(period: Period, day: date) -> date:
    return day if period == "day" else timeutil.week_start(day)


def _key(group_id: int, period: Period, day: date) -> str:
    return f"lb:{group_id}:{period}:{_anchor(period, day).isoformat()}"


async def get_leaderboard(
    db: AsyncSession, redis: Redis, group_id: int, period: Period, day: date
) -> list[dict]:
    key = _key(group_id, period, day)
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)

    first = _anchor(period, day)
    last = day if period == "day" else first + timedelta(days=6)
    tz = group_tz(group_id)
    rows = (
        await db.execute(
            select(GroupDaySolve).where(
                GroupDaySolve.group_id == group_id,
                GroupDaySolve.day >= first,
                GroupDaySolve.day <= last,
            )
        )
    ).scalars()
    solves = [
        leaderboard.Solve(s.user_id, s.day, s.solved_at, timeutil.day_start(s.day, tz))
        for s in rows
    ]
    ranked = leaderboard.daily(solves) if period == "day" else leaderboard.weekly(solves)
    names: dict[int, str] = {}
    if ranked:
        user_rows = await db.execute(
            select(User.id, User.display_name).where(User.id.in_([e.user_id for e in ranked]))
        )
        names = dict(user_rows.tuples().all())
    entries = [
        {
            "rank": e.rank,
            "user_id": e.user_id,
            "display_name": names.get(e.user_id, "?"),
            "solved": e.solved,
            "seconds": e.seconds,
        }
        for e in ranked
    ]
    await redis.set(key, json.dumps(entries), ex=CACHE_TTL_S)
    return entries


async def invalidate(redis: Redis, group_id: int, day: date) -> None:
    await redis.delete(_key(group_id, "day", day), _key(group_id, "week", day))
