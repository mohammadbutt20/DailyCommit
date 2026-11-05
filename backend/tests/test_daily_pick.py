from datetime import date

from dailycommit.domain.daily_pick import Candidate, pick_problem

A = Candidate(1, "a-arrays", ("arrays",))
B = Candidate(2, "b-arrays", ("arrays", "hashing"))
C = Candidate(3, "c-graphs", ("graphs",))


def test_no_candidates():
    assert pick_problem([], []) is None


def test_never_used_problems_come_first():
    history = [(date(2026, 10, 1), 1), (date(2026, 10, 2), 3)]
    assert pick_problem([A, B, C], history) == B


def test_least_recently_used_when_all_used():
    history = [(date(2026, 10, 3), 1), (date(2026, 10, 1), 2), (date(2026, 10, 2), 3)]
    assert pick_problem([A, B, C], history) == B


def test_prefers_a_topic_change_among_equally_fresh_problems():
    # Yesterday was an arrays problem; of the unused B and C, C changes topic.
    history = [(date(2026, 10, 1), 1)]
    assert pick_problem([A, B, C], history) == C


def test_deterministic_tie_break_by_slug():
    assert pick_problem([C, B, A], []) == A


def test_uses_latest_date_per_problem():
    history = [(date(2026, 9, 1), 1), (date(2026, 10, 5), 1), (date(2026, 10, 1), 2)]
    assert pick_problem([A, B], history) == B
