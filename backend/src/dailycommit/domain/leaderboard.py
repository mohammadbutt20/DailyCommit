"""Group leaderboards.

Daily: today's solvers in order of solve time.
Weekly: most daily problems solved; ties go to the lower total time-to-solve
(measured from the start of each day).
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Solve:
    user_id: int
    day: date
    solved_at: datetime
    day_start: datetime


@dataclass(frozen=True)
class Entry:
    rank: int
    user_id: int
    solved: int
    seconds: int  # daily: time-to-solve; weekly: summed time-to-solve


def _ranked(rows: list[tuple[int, int, int]]) -> list[Entry]:
    """rows are (user_id, solved, seconds), already sorted best-first. Equal scores share a rank."""
    entries: list[Entry] = []
    for i, (user_id, solved, seconds) in enumerate(rows):
        prev = entries[-1] if entries else None
        same = prev is not None and (prev.solved, prev.seconds) == (solved, seconds)
        rank = prev.rank if same and prev else i + 1
        entries.append(Entry(rank=rank, user_id=user_id, solved=solved, seconds=seconds))
    return entries


def _seconds(s: Solve) -> int:
    return max(0, int((s.solved_at - s.day_start).total_seconds()))


def daily(solves: Iterable[Solve]) -> list[Entry]:
    rows = sorted(((s.user_id, 1, _seconds(s)) for s in solves), key=lambda r: (r[2], r[0]))
    return _ranked(rows)


def weekly(solves: Iterable[Solve]) -> list[Entry]:
    solved: dict[int, int] = defaultdict(int)
    seconds: dict[int, int] = defaultdict(int)
    for s in solves:
        solved[s.user_id] += 1
        seconds[s.user_id] += _seconds(s)
    rows = sorted(((u, solved[u], seconds[u]) for u in solved), key=lambda r: (-r[1], r[2], r[0]))
    return _ranked(rows)
