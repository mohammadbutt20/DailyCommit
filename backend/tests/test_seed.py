"""The demo history (seed.demo_plan) and its failed tries (seed_attempts): deterministic,
realistic, and truthful to what our judge returns."""

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from dailycommit.domain import streaks, timeutil
from dailycommit.problems.loader import load_judge_packs
from dailycommit.sandbox.languages import PYTHON
from dailycommit.sandbox.runner import TestInput, judge_submission
from dailycommit.seed import DAYS_BACK, MISSED, NAMES, ORDER, _test_counts, demo_plan
from dailycommit.seed_attempts import ATTEMPTS
from tests.conftest import PROBLEMS_DIR

PACKS = {p.slug: p for p in load_judge_packs(PROBLEMS_DIR)}
TZ = ZoneInfo("America/New_York")
TODAY = date(2026, 11, 6)
NOW = datetime(2026, 11, 6, 20, 0, tzinfo=UTC)  # 3 PM in New York
LETTER = {"AC": "A", "WA": "W", "TLE": "T", "skipped": "s"}


def plan(now=NOW):
    return demo_plan(TODAY, TZ, now, _test_counts(PACKS))


def test_every_seeded_problem_is_a_judge_pack():
    assert set(ORDER) <= set(PACKS) and len(set(ORDER)) == len(ORDER) == 20


def test_deterministic():
    assert plan() == plan()


def test_a_problem_per_day_never_repeated_within_20_days():
    days = plan().days
    assert [d for d, _ in days] == [TODAY - timedelta(days=b) for b in range(DAYS_BACK, -1, -1)]
    assert days[-1][1] == "best-time-to-buy-and-sell-stock"
    last_seen: dict[str, int] = {}
    for i, (_, slug) in enumerate(days):
        assert i - last_seen.get(slug, -100) >= 20, slug
        last_seen[slug] = i


def test_streaks_from_the_real_rules_best_8_current_5():
    p = plan()
    members = [
        streaks.Member(i, timeutil.day_start(p.start, TZ) + timedelta(hours=20)) for i in range(4)
    ]
    ids = {name: i for i, name in enumerate(NAMES)}
    streak, broken = streaks.Streak(0, 0), []
    for day, _ in p.days[:-1]:  # every day before today
        solved = {ids[s.member] for s in p.submissions if s.credits and s.day == day}
        outcome = streaks.evaluate_day(members, solved, timeutil.day_start(day, TZ))
        if not outcome.kept:
            broken.append((TODAY - day).days)
        streak = streaks.apply_outcome(streak, outcome)
    assert sorted(broken, reverse=True) == sorted(MISSED, reverse=True) == [13, 6]
    assert (streak.current, streak.best) == (5, 8)


def test_times_are_inside_their_day_varied_and_never_in_the_future():
    p = plan()
    for s in p.submissions:
        assert timeutil.local_day(s.at, TZ) == s.day
        assert s.at <= NOW
    solve_minutes = {s.at.astimezone(TZ).strftime("%H:%M") for s in p.submissions if s.credits}
    assert len(solve_minutes) > 60  # not a handful of fixed times
    hours = Counter(s.at.astimezone(TZ).hour for s in p.submissions)
    assert min(hours) <= 8 and max(hours) >= 22  # mornings to late evenings


def test_today_only_alice_once_her_time_has_come():
    today = [s for s in plan().submissions if s.day == TODAY]
    assert [(s.member, s.kind, s.verdict) for s in today] == [("Alice", "submit", "AC")]
    early = demo_plan(TODAY, TZ, datetime(2026, 11, 6, 9, 0, tzinfo=UTC), _test_counts(PACKS))
    assert [s for s in early.submissions if s.day == TODAY] == []  # 4 AM in New York


def test_languages_verdicts_and_bobs_practice():
    subs = plan().submissions
    assert {s.language for s in subs} == {"python", "java", "cpp"}
    assert {s.verdict for s in subs} == {"AC", "WA", "TLE"}
    for s in subs:
        if (
            s.verdict != "AC"
            and s.kind == "submit"
            and MISSED.get((TODAY - s.day).days) != s.member
        ):
            later = [
                x
                for x in subs
                if (x.member, x.day, x.slug, x.verdict) == (s.member, s.day, s.slug, "AC")
            ]
            assert later and later[0].at > s.at  # a failed try comes before the Accepted
    bob = [s for s in subs if s.member == "Bob"]
    assert Counter(s.kind for s in bob)["practice"] >= 5
    assert any(s.kind == "practice" and s.verdict == "WA" for s in bob)
    assert any(s.kind == "run" for s in bob)
    for s in subs:
        n_samples, total = _test_counts(PACKS)[s.slug]
        assert len(s.results) == (n_samples if s.kind == "run" else total)


@pytest.mark.parametrize(
    "name", [n for n, a in ATTEMPTS.items() if a.verdict == "WA"], ids=lambda n: n
)
def test_seeded_wrong_answers_are_what_our_judge_returns(name, local_sandbox):
    """The demo never shows a verdict our judge wouldn't give (TLE ones: sandbox suite)."""
    a = ATTEMPTS[name]
    pack = PACKS[a.slug]
    tests = [
        TestInput(t.input, t.expected, t.sample)
        for t in sorted(pack.tests, key=lambda t: not t.sample)
    ]
    report = judge_submission(
        local_sandbox, PYTHON, a.code, pack.signature, tests, pack.compare, pack.limits.model_dump()
    )
    assert report.verdict == a.verdict
    assert "".join(LETTER[r.verdict] for r in report.results) == a.results
    wrong_samples = {
        r.ordinal: r.actual for r in report.results if tests[r.ordinal].sample and r.verdict == "WA"
    }
    assert wrong_samples == a.sample_outputs
