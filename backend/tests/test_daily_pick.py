from datetime import date

from dailycommit.domain.daily_pick import Candidate, daily_pool, pick_problem

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


# --- daily_pool: what auto-pick may choose from -------------------------------------------

LC_JUDGED = Candidate(10, "two-sum", ("arrays",), source="leetcode", judgeable=True)
LC_UNJUDGED = Candidate(11, "lru-cache", ("design",), source="leetcode", judgeable=False)
LOCAL = Candidate(12, "commit-pair", ("arrays",), source="local", judgeable=True)
LOCAL_UNJUDGED = Candidate(13, "broken", ("arrays",), source="local", judgeable=False)


def test_pool_prefers_judgeable_leetcode_problems():
    assert daily_pool([LC_JUDGED, LC_UNJUDGED, LOCAL]) == [LC_JUDGED]


def test_pool_never_includes_a_problem_without_a_judge_pack():
    # Plenty of imported LeetCode problems, none judgeable: fall back to local ones.
    assert daily_pool([LC_UNJUDGED, LOCAL]) == [LOCAL]
    assert pick_problem(daily_pool([LC_UNJUDGED, LOCAL]), []) == LOCAL


def test_pool_excludes_unjudgeable_local_problems():
    assert daily_pool([LOCAL_UNJUDGED, LOCAL]) == [LOCAL]


def test_pool_is_empty_when_nothing_is_judgeable():
    assert daily_pool([LC_UNJUDGED, LOCAL_UNJUDGED]) == []
    assert pick_problem(daily_pool([LC_UNJUDGED]), []) is None
