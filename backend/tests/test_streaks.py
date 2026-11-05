from datetime import UTC, datetime, timedelta

from dailycommit.domain.streaks import DayOutcome, Member, Streak, apply_outcome, evaluate_day

DAY_START = datetime(2026, 10, 20, 4, 0, tzinfo=UTC)
BEFORE = DAY_START - timedelta(days=3)
DURING = DAY_START + timedelta(hours=15)


def test_everyone_eligible_solved_keeps_streak():
    members = [Member(1, BEFORE), Member(2, BEFORE)]
    assert evaluate_day(members, [1, 2], DAY_START) == DayOutcome(2, 2, True)


def test_one_eligible_member_missing_breaks_streak():
    members = [Member(1, BEFORE), Member(2, BEFORE)]
    assert evaluate_day(members, [1], DAY_START) == DayOutcome(2, 1, False)


def test_member_who_joined_during_the_day_is_not_required():
    members = [Member(1, BEFORE), Member(2, DURING)]
    assert evaluate_day(members, [1], DAY_START).kept is True


def test_joining_exactly_at_day_start_is_not_eligible():
    members = [Member(1, BEFORE), Member(2, DAY_START)]
    assert evaluate_day(members, [1], DAY_START).eligible_count == 1


def test_paused_member_is_not_required():
    members = [Member(1, BEFORE), Member(2, BEFORE, paused=True)]
    assert evaluate_day(members, [1], DAY_START).kept is True


def test_solves_by_ineligible_members_do_not_count():
    members = [Member(1, BEFORE), Member(2, DURING)]
    outcome = evaluate_day(members, [2], DAY_START)
    assert outcome == DayOutcome(1, 0, False)


def test_no_eligible_members_leaves_streak_unchanged():
    outcome = evaluate_day([Member(1, DURING)], [1], DAY_START)
    assert outcome.kept is None
    assert apply_outcome(Streak(5, 7), outcome) == Streak(5, 7)


def test_empty_group_is_unchanged():
    assert evaluate_day([], [], DAY_START).kept is None


def test_apply_kept_increments_and_tracks_best():
    assert apply_outcome(Streak(3, 3), DayOutcome(2, 2, True)) == Streak(4, 4)
    assert apply_outcome(Streak(3, 9), DayOutcome(2, 2, True)) == Streak(4, 9)


def test_apply_broken_resets_but_keeps_best():
    assert apply_outcome(Streak(6, 6), DayOutcome(2, 1, False)) == Streak(0, 6)
