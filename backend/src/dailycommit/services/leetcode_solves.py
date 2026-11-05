"""Credit solves made on leetcode.com.

For each member with a verified LeetCode account who still owes a LeetCode problem on an
unevaluated day, read their recent accepted submissions (public data) and credit any that
match, via the same `record_solves` the judge uses, so streak and leaderboard rules are
identical. Runs from the scheduler just before each rollover, and on demand ("Check now").
"""

import asyncio
import logging
from dataclasses import dataclass

import httpx
from redis.asyncio import Redis
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.leetcode import client as lc
from dailycommit.models import (
    Group,
    GroupDailyProblem,
    GroupDaySolve,
    GroupMember,
    Problem,
    User,
)
from dailycommit.services.solves import announce_solves, record_solves

log = logging.getLogger(__name__)
PAUSE_BETWEEN_USERS_S = 0.3  # be polite to an unofficial API


@dataclass(frozen=True)
class Owed:
    user_id: int
    username: str
    problem_id: int
    slug: str


async def owed_problems(db: AsyncSession, user_id: int | None = None) -> list[Owed]:
    """LeetCode problems that linked members haven't solved yet, on days not yet evaluated."""
    q = (
        select(User.id, User.leetcode_username, Problem.id, Problem.slug)
        .join(GroupMember, GroupMember.user_id == User.id)
        .join(Group, Group.id == GroupMember.group_id)
        .join(
            GroupDailyProblem,
            and_(
                GroupDailyProblem.group_id == Group.id,
                GroupDailyProblem.day > Group.last_rolled_day,
            ),
        )
        .join(
            Problem, and_(Problem.id == GroupDailyProblem.problem_id, Problem.source == "leetcode")
        )
        .outerjoin(
            GroupDaySolve,
            and_(
                GroupDaySolve.group_id == Group.id,
                GroupDaySolve.day == GroupDailyProblem.day,
                GroupDaySolve.user_id == User.id,
            ),
        )
        .where(User.leetcode_username.is_not(None), GroupDaySolve.user_id.is_(None))
        .distinct()
    )
    if user_id is not None:
        q = q.where(User.id == user_id)
    return [Owed(*row) for row in (await db.execute(q)).all()]


async def check_user(
    db: AsyncSession, redis: Redis, http: httpx.AsyncClient, user: User, owed: list[Owed]
) -> list[tuple[int, str]]:
    """Credit this user's matching LeetCode accepts. Commits. Returns (group_id, slug) credited.
    Raises LeetCodeError if LeetCode can't be read."""
    by_slug = {o.slug: o.problem_id for o in owed if o.user_id == user.id}
    if not by_slug or not user.leetcode_username:
        return []
    accepted = await lc.recent_accepted(http, user.leetcode_username)
    announcements = []
    for ac in sorted(accepted, key=lambda a: a.at):  # earliest accept of the day counts
        problem_id = by_slug.get(ac.slug)
        if problem_id is None:
            continue
        credited = await record_solves(db, user.id, problem_id, ac.at, external_ref=ac.id)
        if credited:
            announcements.append((credited, ac))
    await db.commit()
    done = []
    for credited, ac in announcements:
        await announce_solves(
            redis,
            credited,
            user_id=user.id,
            display_name=user.display_name,
            problem_slug=ac.slug,
            solved_at=ac.at,
        )
        done += [(group_id, ac.slug) for group_id, _ in credited]
    return done


async def check_all(db: AsyncSession, redis: Redis, http: httpx.AsyncClient) -> int:
    """Scheduler entry point. One LeetCode request per member who owes something."""
    owed = await owed_problems(db)
    await db.commit()  # end the read; each user gets their own transaction
    user_ids = sorted({o.user_id for o in owed})
    credited = 0
    for n, user_id in enumerate(user_ids):
        if n:
            await asyncio.sleep(PAUSE_BETWEEN_USERS_S)
        user = await db.get(User, user_id)
        if user is None:
            continue
        try:
            credited += len(await check_user(db, redis, http, user, owed))
        except lc.LeetCodeError as e:
            await db.rollback()
            log.warning("LeetCode check failed for user %s: %s", user_id, e)
    return credited
