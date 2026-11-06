"""Past problems, practice, "my history" and stats, through the real API and a real Postgres.

The app runs in-process (httpx ASGITransport). Only the DB session, the signed-in user (picked
per request with an `x-test-user` header) and Redis/arq are overridden.
"""

from datetime import UTC, date, datetime, timedelta

import httpx
from fastapi import Request
from sqlalchemy import func, select

from dailycommit.api.deps import current_user, get_arq, get_redis
from dailycommit.api.main import app
from dailycommit.db import get_db
from dailycommit.jobs import worker
from dailycommit.models import (
    Group,
    GroupDailyProblem,
    GroupDaySolve,
    GroupMember,
    GroupStreakDay,
    Problem,
    Submission,
    TestCase,
    User,
)
from tests.conftest import LocalProcessSandbox
from tests.pg import FakeRedis

AC_CODE = "class Solution:\n    def add(self, a, b):\n        return a + b\n"
SIGNATURE = {
    "function": "add",
    "params": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
    "returns": "int",
}


class FakeArq:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    async def enqueue_job(self, *args):
        self.jobs.append(args)


class FakeRateLimitRedis(FakeRedis):
    async def incr(self, key):
        return 1

    async def expire(self, key, seconds):
        return True


def client(factory, arq=None) -> httpx.AsyncClient:
    async def db_override():
        async with factory() as session:
            yield session

    async def user_override(request: Request) -> User:
        async with factory() as session:
            return await session.get(User, int(request.headers["x-test-user"]))

    app.dependency_overrides = {
        get_db: db_override,
        current_user: user_override,
        get_redis: lambda: FakeRateLimitRedis(),
        get_arq: lambda: arq or FakeArq(),
    }
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def as_user(user_id: int) -> dict[str, str]:
    return {"x-test-user": str(user_id)}


async def seed(factory) -> dict:
    """Ann and Bob in group G (UTC); Carl alone in group H. G's problems: day -2, day -1, today,
    and a leader's pick for tomorrow (which must never show up in history)."""
    today = datetime.now(UTC).date()
    long_ago = datetime.now(UTC) - timedelta(days=5)
    async with factory() as s, s.begin():
        ann, bob, carl = (
            User(display_name="Ann"),
            User(display_name="Bob"),
            User(display_name="Carl"),
        )
        s.add_all([ann, bob, carl])
        await s.flush()
        g = Group(
            name="G",
            invite_code="HISTORYG",
            timezone="UTC",
            created_by=ann.id,
            last_rolled_day=today - timedelta(days=1),
            current_streak=1,
            best_streak=3,
        )
        h = Group(
            name="H",
            invite_code="HISTORYH",
            timezone="UTC",
            created_by=carl.id,
            last_rolled_day=today,
        )
        problems = [
            Problem(
                slug=f"p{i}",
                title=f"Problem {i}",
                difficulty=["easy", "medium", "hard"][i % 3],
                topics=["math"],
                statement_md="",
                content_hash="x",
                signature=SIGNATURE,
                compare="exact",
                limits={"time_ms": 1000, "memory_mb": 64},
            )
            for i in range(3)
        ]
        s.add_all([g, h, *problems])
        await s.flush()
        p0, p1, p2 = problems
        s.add_all(
            [
                GroupMember(group_id=g.id, user_id=ann.id, role="leader", joined_at=long_ago),
                GroupMember(group_id=g.id, user_id=bob.id, joined_at=long_ago),
                GroupMember(group_id=h.id, user_id=carl.id, role="leader", joined_at=long_ago),
                *(
                    TestCase(
                        problem_id=p.id,
                        ordinal=o,
                        is_sample=o == 0,
                        input={"a": o, "b": 1},
                        expected=o + 1,
                    )
                    for p in problems
                    for o in (0, 1)
                ),
                GroupDailyProblem(group_id=g.id, day=today - timedelta(days=2), problem_id=p0.id),
                GroupDailyProblem(group_id=g.id, day=today - timedelta(days=1), problem_id=p1.id),
                GroupDailyProblem(group_id=g.id, day=today, problem_id=p2.id),
                GroupDailyProblem(group_id=g.id, day=today + timedelta(days=1), problem_id=p0.id),
                GroupStreakDay(
                    group_id=g.id,
                    day=today - timedelta(days=2),
                    eligible_count=2,
                    solved_count=1,
                    kept=False,
                ),
                GroupStreakDay(
                    group_id=g.id,
                    day=today - timedelta(days=1),
                    eligible_count=2,
                    solved_count=2,
                    kept=True,
                ),
            ]
        )
        # Ann: AC + WA on p0 (python), AC on p1 (java), a samples-only run, and an IE.
        subs = [
            Submission(
                user_id=ann.id,
                problem_id=p0.id,
                group_id=g.id,
                language="python",
                kind="submit",
                code="a1",
                status="done",
                verdict="WA",
                passed=1,
                total=2,
            ),
            Submission(
                user_id=ann.id,
                problem_id=p0.id,
                group_id=g.id,
                language="python",
                kind="submit",
                code="a2",
                status="done",
                verdict="AC",
                passed=2,
                total=2,
            ),
            Submission(
                user_id=ann.id,
                problem_id=p1.id,
                group_id=g.id,
                language="java",
                kind="submit",
                code="a3",
                status="done",
                verdict="AC",
                passed=2,
                total=2,
            ),
            Submission(
                user_id=ann.id,
                problem_id=p1.id,
                group_id=g.id,
                language="java",
                kind="run",
                code="a4",
                status="done",
                verdict="AC",
                passed=1,
                total=1,
            ),
            Submission(
                user_id=ann.id,
                problem_id=p1.id,
                group_id=None,
                language="cpp",
                kind="submit",
                code="a5",
                status="done",
                verdict="IE",
            ),
            Submission(
                user_id=bob.id,
                problem_id=p1.id,
                group_id=g.id,
                language="python",
                kind="submit",
                code="secret bob code",
                status="done",
                verdict="AC",
                passed=2,
                total=2,
            ),
        ]
        s.add_all(subs)
        await s.flush()
        s.add_all(
            [
                GroupDaySolve(
                    group_id=g.id,
                    day=today - timedelta(days=2),
                    user_id=ann.id,
                    submission_id=subs[1].id,
                    solved_at=long_ago,
                ),
                GroupDaySolve(
                    group_id=g.id,
                    day=today - timedelta(days=1),
                    user_id=ann.id,
                    submission_id=subs[2].id,
                    solved_at=long_ago,
                ),
                GroupDaySolve(
                    group_id=g.id,
                    day=today - timedelta(days=1),
                    user_id=bob.id,
                    submission_id=subs[5].id,
                    solved_at=long_ago,
                ),
            ]
        )
    return {
        "today": today,
        "ann": ann.id,
        "bob": bob.id,
        "carl": carl.id,
        "g": g.id,
        "h": h.id,
        "p2": p2.slug,
        "ann_subs": [x.id for x in subs[:5]],
        "bob_sub": subs[5].id,
    }


def test_history_lists_past_days_newest_first_and_never_the_future(db):
    async def scenario(factory):
        ids = await seed(factory)
        today: date = ids["today"]
        async with client(factory) as c:
            r = await c.get(f"/api/groups/{ids['g']}/history", headers=as_user(ids["ann"]))
        assert r.status_code == 200
        days = r.json()
        assert [d["day"] for d in days] == [str(today - timedelta(days=n)) for n in (0, 1, 2)]
        assert [d["is_today"] for d in days] == [True, False, False]
        assert [d["problem"]["slug"] for d in days] == ["p2", "p1", "p0"]
        assert [d["solved_by_me"] for d in days] == [False, True, True]
        assert [(d["solved_count"], d["member_count"]) for d in days] == [(0, 2), (2, 2), (1, 2)]
        assert [d["kept"] for d in days] == [None, True, False]

    db(scenario)


def test_history_is_members_only_and_one_day_can_be_opened(db):
    async def scenario(factory):
        ids = await seed(factory)
        today: date = ids["today"]
        async with client(factory) as c:
            outsider = await c.get(f"/api/groups/{ids['g']}/history", headers=as_user(ids["carl"]))
            one = await c.get(
                f"/api/groups/{ids['g']}/history/{today - timedelta(days=1)}",
                headers=as_user(ids["bob"]),
            )
            future = await c.get(
                f"/api/groups/{ids['g']}/history/{today + timedelta(days=1)}",
                headers=as_user(ids["ann"]),
            )
            empty = await c.get(
                f"/api/groups/{ids['g']}/history/{today - timedelta(days=9)}",
                headers=as_user(ids["ann"]),
            )
        assert outsider.status_code == 404
        assert (
            one.status_code == 200
            and one.json()["problem"]["slug"] == "p1"
            and one.json()["solved_by_me"]
        )
        assert future.status_code == 404  # tomorrow's pick stays hidden
        assert empty.status_code == 404

    db(scenario)


def test_my_submissions_are_mine_only_newest_first_and_paged(db):
    async def scenario(factory):
        ids = await seed(factory)
        async with client(factory) as c:
            page1 = (await c.get("/api/me/submissions?limit=3", headers=as_user(ids["ann"]))).json()
            page2 = (
                await c.get(
                    f"/api/me/submissions?limit=3&before_id={page1['next_before_id']}",
                    headers=as_user(ids["ann"]),
                )
            ).json()
            bobs = (await c.get("/api/me/submissions", headers=as_user(ids["bob"]))).json()
            carls = (await c.get("/api/me/submissions", headers=as_user(ids["carl"]))).json()
            peek = await c.get(f"/api/submissions/{ids['bob_sub']}", headers=as_user(ids["ann"]))
            own = await c.get(f"/api/submissions/{ids['bob_sub']}", headers=as_user(ids["bob"]))
        seen = [s["id"] for s in page1["items"] + page2["items"]]
        assert seen == sorted(ids["ann_subs"], reverse=True)
        assert page2["next_before_id"] is None
        assert ids["bob_sub"] not in seen
        assert [s["id"] for s in bobs["items"]] == [ids["bob_sub"]]
        assert carls["items"] == []
        first = page1["items"][0]  # the newest: the IE with no group
        assert (first["group"], first["language"], first["verdict"]) == (None, "cpp", "IE")
        assert page1["items"][1]["group"] == {"id": ids["g"], "name": "G"}
        assert peek.status_code == 404  # someone else's submission doesn't exist for you
        assert own.status_code == 200 and own.json()["code"] == "secret bob code"

    db(scenario)


def test_my_stats(db):
    async def scenario(factory):
        ids = await seed(factory)
        async with client(factory) as c:
            ann = (await c.get("/api/me/stats", headers=as_user(ids["ann"]))).json()
            carl = (await c.get("/api/me/stats", headers=as_user(ids["carl"]))).json()
        # Judged: WA, AC, AC (the run and the IE don't count) -> 2/3.
        assert (ann["submissions"], ann["accepted"]) == (3, 2)
        assert round(ann["accepted_rate"], 4) == round(2 / 3, 4)
        assert ann["problems_solved"] == 2
        assert ann["by_language"] == {"java": 1, "python": 1}
        assert ann["by_difficulty"] == {"easy": 1, "medium": 1}
        assert ann["streaks"] == [
            {"group_id": ids["g"], "group_name": "G", "current_streak": 1, "best_streak": 3}
        ]
        assert carl["accepted_rate"] is None and carl["problems_solved"] == 0

    db(scenario)


def test_submissions_remember_their_group_and_only_your_groups(db):
    async def scenario(factory):
        ids = await seed(factory)
        arq = FakeArq()
        body = {"problem_slug": "p0", "language": "python", "kind": "practice", "code": AC_CODE}
        async with client(factory, arq) as c:
            mine = await c.post(
                "/api/submissions", json={**body, "group_id": ids["g"]}, headers=as_user(ids["ann"])
            )
            theirs = await c.post(
                "/api/submissions", json={**body, "group_id": ids["h"]}, headers=as_user(ids["ann"])
            )
        assert mine.status_code == 201 and mine.json()["group"] == {"id": ids["g"], "name": "G"}
        assert mine.json()["kind"] == "practice"
        assert theirs.status_code == 404
        assert len(arq.jobs) == 1

    db(scenario)


def test_practice_never_changes_a_streak_or_a_day(db):
    async def scenario(factory):
        ids = await seed(factory)
        today = ids["today"]

        async def snapshot():
            async with factory() as s:
                solves = await s.scalar(select(func.count()).select_from(GroupDaySolve))
                days = (
                    await s.execute(
                        select(GroupStreakDay.day, GroupStreakDay.solved_count, GroupStreakDay.kept)
                    )
                ).all()
                g = await s.get(Group, ids["g"])
                return solves, sorted(days), g.current_streak, g.best_streak

        async def judge(kind: str) -> str:
            async with factory() as s, s.begin():
                problem_id = await s.scalar(select(Problem.id).where(Problem.slug == ids["p2"]))
                sub = Submission(
                    user_id=ids["bob"],
                    problem_id=problem_id,
                    group_id=ids["g"],
                    language="python",
                    kind=kind,
                    code=AC_CODE,
                )
                s.add(sub)
                await s.flush()
                sid = sub.id
            ctx = {"redis": FakeRedis(), "sandbox": LocalProcessSandbox(), "job_try": 1}
            return await worker.run_submission(ctx, sid)

        before = await snapshot()
        # A practice AC on the problem that is today's: judged on every test, credits nothing.
        assert await judge("practice") == "AC"
        assert await snapshot() == before
        # The same code as a real submit does count, which shows the setup would have credited.
        assert await judge("submit") == "AC"
        async with factory() as s:
            credited = await s.scalar(
                select(func.count()).where(
                    GroupDaySolve.user_id == ids["bob"], GroupDaySolve.day == today
                )
            )
        assert credited == 1

    db(scenario)
