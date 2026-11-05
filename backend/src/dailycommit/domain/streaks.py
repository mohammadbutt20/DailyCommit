"""Group streak rule.

A member is *eligible* for a day if they joined before the day started and are not paused.
The streak grows if every eligible member solved that day's problem, and resets otherwise.
A day with nobody eligible leaves the streak unchanged.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Member:
    user_id: int
    joined_at: datetime
    paused: bool = False


@dataclass(frozen=True)
class DayOutcome:
    eligible_count: int
    solved_count: int
    kept: bool | None  # None = nobody eligible, streak unchanged


@dataclass(frozen=True)
class Streak:
    current: int
    best: int


def eligible_members(members: Iterable[Member], day_start: datetime) -> list[Member]:
    return [m for m in members if m.joined_at < day_start and not m.paused]


def evaluate_day(
    members: Iterable[Member], solved_user_ids: Iterable[int], day_start: datetime
) -> DayOutcome:
    eligible = {m.user_id for m in eligible_members(members, day_start)}
    solved = eligible & set(solved_user_ids)
    if not eligible:
        return DayOutcome(eligible_count=0, solved_count=0, kept=None)
    return DayOutcome(
        eligible_count=len(eligible), solved_count=len(solved), kept=solved == eligible
    )


def apply_outcome(streak: Streak, outcome: DayOutcome) -> Streak:
    if outcome.kept is None:
        return streak
    if not outcome.kept:
        return Streak(current=0, best=streak.best)
    current = streak.current + 1
    return Streak(current=current, best=max(streak.best, current))
