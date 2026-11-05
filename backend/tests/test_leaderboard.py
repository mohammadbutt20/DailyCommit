from datetime import UTC, date, datetime, timedelta

from dailycommit.domain.leaderboard import Solve, daily, weekly

D1, D2 = date(2026, 10, 19), date(2026, 10, 20)
S1 = datetime(2026, 10, 19, 4, tzinfo=UTC)
S2 = S1 + timedelta(days=1)


def solve(user: int, day: date, start: datetime, minutes: int) -> Solve:
    return Solve(user, day, start + timedelta(minutes=minutes), start)


def test_daily_orders_by_solve_time():
    entries = daily([solve(1, D1, S1, 90), solve(2, D1, S1, 30), solve(3, D1, S1, 60)])
    assert [(e.rank, e.user_id, e.seconds) for e in entries] == [
        (1, 2, 1800),
        (2, 3, 3600),
        (3, 1, 5400),
    ]


def test_daily_ties_share_rank():
    entries = daily([solve(1, D1, S1, 10), solve(2, D1, S1, 10), solve(3, D1, S1, 20)])
    assert [e.rank for e in entries] == [1, 1, 3]


def test_weekly_more_solves_beats_faster():
    entries = weekly(
        [
            solve(1, D1, S1, 600),
            solve(1, D2, S2, 600),
            solve(2, D1, S1, 1),
        ]
    )
    assert [(e.user_id, e.solved) for e in entries] == [(1, 2), (2, 1)]


def test_weekly_tie_on_count_broken_by_total_time():
    entries = weekly(
        [solve(1, D1, S1, 50), solve(1, D2, S2, 50), solve(2, D1, S1, 20), solve(2, D2, S2, 20)]
    )
    assert [e.user_id for e in entries] == [2, 1]
    assert entries[0].seconds == 40 * 60


def test_empty():
    assert daily([]) == []
    assert weekly([]) == []
