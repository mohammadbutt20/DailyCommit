"""Demo data: `python -m dailycommit.seed` (after `make sync-problems`). Safe to re-run.

Creates dev users Alice (leader), Bob, Chen and Dana in "Pledge Class Demo" (invite DEMO2026)
with a week of history: everyone solves days -7..-4, Bob misses day -3, everyone solves -2 and
-1. The real rollover logic then computes the streak (current 2, best 4). Today only Alice has
solved, so logging in as anyone else and solving shows the live flow.
"""

import asyncio
from datetime import timedelta

from sqlalchemy import select

from dailycommit.api.auth.sessions import user_for_identity
from dailycommit.db import SessionLocal
from dailycommit.domain import timeutil
from dailycommit.models import (
    Group,
    GroupDaySolve,
    GroupMember,
    Problem,
    Submission,
    utcnow,
)
from dailycommit.services.clock import group_tz, today
from dailycommit.services.daily import daily_problem, ensure_daily_problem
from dailycommit.services.rollover import rollover_all

INVITE = "DEMO2026"
NAMES = ["Alice", "Bob", "Chen", "Dana"]


async def seed() -> None:
    async with SessionLocal() as db:
        if await db.scalar(select(Group.id).where(Group.invite_code == INVITE)):
            print("demo group already exists; nothing to do")
            return
        if not await db.scalar(select(Problem.id).where(Problem.retired.is_(False))):
            raise SystemExit("no problems in the database; run `make sync-problems` first")

        now = utcnow()
        tz = group_tz()
        day0 = today(now=now)
        users = [await user_for_identity(db, "dev", n.lower(), n) for n in NAMES]
        alice, bob = users[0], users[1]

        group = Group(
            name="Pledge Class Demo",
            invite_code=INVITE,
            created_by=alice.id,
            created_at=now - timedelta(days=10),
            last_rolled_day=day0 - timedelta(days=8),
        )
        db.add(group)
        await db.flush()
        for u in users:
            db.add(
                GroupMember(
                    group_id=group.id,
                    user_id=u.id,
                    role="leader" if u is alice else "member",
                    joined_at=now - timedelta(days=10),
                )
            )

        async def solve(user_id: int, day, solved_at) -> None:
            problem = await daily_problem(db, group.id, day)
            assert problem is not None
            sub = Submission(
                user_id=user_id,
                problem_id=problem.id,
                language="python",
                kind="submit",
                code="# seeded demo solve\n",
                status="done",
                verdict="AC",
                created_at=solved_at,
                finished_at=solved_at,
            )
            db.add(sub)
            await db.flush()
            db.add(
                GroupDaySolve(
                    group_id=group.id,
                    day=day,
                    user_id=user_id,
                    submission_id=sub.id,
                    solved_at=solved_at,
                )
            )

        for back in range(7, 0, -1):
            day = day0 - timedelta(days=back)
            await ensure_daily_problem(db, group.id, day)
            start = timeutil.day_start(day, tz)
            for n, u in enumerate(users):
                if back == 3 and u is bob:
                    continue
                await solve(u.id, day, start + timedelta(hours=9 + 2 * n, minutes=7 * back))

        await ensure_daily_problem(db, group.id, day0)
        await solve(alice.id, day0, max(timeutil.day_start(day0, tz), now - timedelta(minutes=30)))
        await db.commit()

        await rollover_all(db, now)
        await db.refresh(group)
        print(
            f"seeded {group.name!r} (invite {INVITE}) with users {', '.join(NAMES)}; "
            f"streak {group.current_streak}, best {group.best_streak}"
        )


if __name__ == "__main__":
    asyncio.run(seed())
