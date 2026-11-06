"""The group activity feed: merging history, stable ids, and live events carrying the same ids
as the history endpoint (so the browser can deduplicate)."""

import asyncio
import json
from datetime import UTC, date, datetime, timedelta

from dailycommit.domain.activity import Activity, join_id, recent_activity, solve_id
from dailycommit.models import GroupDaySolve, GroupMember
from dailycommit.services.activity import group_activity
from dailycommit.services.solves import announce_solves

T = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
DAY = date(2026, 11, 5)


def solve(user_id: int, minutes_ago: int, day: date = DAY) -> Activity:
    return Activity(
        solve_id(day, user_id), "solve", user_id, f"u{user_id}", T - timedelta(minutes=minutes_ago)
    )


def join(user_id: int, minutes_ago: int) -> Activity:
    return Activity(
        join_id(user_id), "join", user_id, f"u{user_id}", T - timedelta(minutes=minutes_ago)
    )


# --- domain --------------------------------------------------------------------------------


def test_ids_name_the_underlying_row():
    assert solve_id(DAY, 4) == "solve:2026-11-05:4"
    assert solve_id(DAY, 4) != solve_id(DAY + timedelta(days=1), 4)  # one solve per day
    assert join_id(4) == "join:4"


def test_newest_first_across_kinds():
    got = recent_activity([join(1, 60), solve(2, 5), solve(1, 30)], limit=10)
    assert [a.id for a in got] == [solve_id(DAY, 2), solve_id(DAY, 1), join_id(1)]


def test_duplicates_collapse():
    got = recent_activity([solve(2, 5), solve(2, 5), join(2, 9), join(2, 9)], limit=10)
    assert [a.id for a in got] == [solve_id(DAY, 2), join_id(2)]


def test_limit_keeps_the_newest():
    items = [solve(u, minutes_ago=u) for u in range(1, 31)]
    got = recent_activity(items, limit=20)
    assert len(got) == 20 and got[0].user_id == 1 and got[-1].user_id == 20
    assert recent_activity(items, limit=0) == []


def test_equal_times_break_by_id_descending():
    got = recent_activity([join(1, 0), join(2, 0)], limit=10)
    assert [a.id for a in got] == ["join:2", "join:1"]


# --- service: rows -> activity -------------------------------------------------------------


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeDB:
    """Answers group_activity's two queries (solves, then joins) with canned rows."""

    def __init__(self, solves, joins):
        self.results = [FakeResult(solves), FakeResult(joins)]
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)


def test_group_activity_builds_the_feed_from_solves_and_joins():
    solves = [
        (
            GroupDaySolve(group_id=7, day=DAY, user_id=4, solved_at=T - timedelta(minutes=5)),
            "Bob",
            "two-sum",
        ),
        (
            GroupDaySolve(
                group_id=7, day=DAY - timedelta(days=1), user_id=3, solved_at=T - timedelta(days=1)
            ),
            "Alice",
            None,  # problem row gone: still shown
        ),
    ]
    joins = [(GroupMember(group_id=7, user_id=9, joined_at=T - timedelta(hours=2)), "Zed")]
    db = FakeDB(solves, joins)
    got = asyncio.run(group_activity(db, 7, limit=20))  # type: ignore[arg-type]
    assert got == [
        Activity("solve:2026-11-05:4", "solve", 4, "Bob", T - timedelta(minutes=5), "two-sum"),
        Activity("join:9", "join", 9, "Zed", T - timedelta(hours=2)),
        Activity("solve:2026-11-04:3", "solve", 3, "Alice", T - timedelta(days=1), None),
    ]
    # Both queries are scoped to the group and bounded by the limit.
    for statement in db.statements:
        params = statement.compile().params
        assert 7 in params.values() and 20 in params.values()


def test_group_activity_caps_the_merged_feed():
    solves = [
        (
            GroupDaySolve(group_id=7, day=DAY, user_id=u, solved_at=T - timedelta(minutes=u)),
            "x",
            None,
        )
        for u in range(3)
    ]
    joins = [
        (GroupMember(group_id=7, user_id=u, joined_at=T - timedelta(minutes=10 + u)), "x")
        for u in range(3)
    ]
    got = asyncio.run(group_activity(FakeDB(solves, joins), 7, limit=4))  # type: ignore[arg-type]
    assert [a.id for a in got] == [solve_id(DAY, 0), solve_id(DAY, 1), solve_id(DAY, 2), "join:0"]


# --- live events carry the history's ids ---------------------------------------------------


class FakeRedis:
    def __init__(self):
        self.published: list[tuple[str, dict]] = []

    async def delete(self, *keys):
        return len(keys)

    async def publish(self, channel, message):
        self.published.append((channel, json.loads(message)))


def test_live_solve_event_has_the_same_id_as_history():
    redis = FakeRedis()
    asyncio.run(
        announce_solves(
            redis,  # type: ignore[arg-type]
            [(7, DAY), (8, DAY)],
            user_id=4,
            display_name="Bob",
            problem_slug="two-sum",
            solved_at=T,
        )
    )
    assert [channel for channel, _ in redis.published] == ["group:7", "group:8"]
    for _, msg in redis.published:
        assert msg["event"] == "solve"
        assert msg["data"]["id"] == solve_id(DAY, 4) == "solve:2026-11-05:4"
        assert msg["data"]["at"] == T.isoformat()
