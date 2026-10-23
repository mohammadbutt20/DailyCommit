"""Choosing a group's next daily problem."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Candidate:
    problem_id: int
    slug: str
    topics: tuple[str, ...]


def pick_problem(
    candidates: Sequence[Candidate], history: Sequence[tuple[date, int]]
) -> Candidate | None:
    """Least-recently-used problem for this group, avoiding the previous problem's topics.

    `history` is the group's past (day, problem_id) assignments. Never-assigned problems
    come first; ties break toward a topic change, then by slug so the choice is deterministic.
    """
    if not candidates:
        return None
    last_used: dict[int, date] = {}
    for day, problem_id in history:
        if problem_id not in last_used or day > last_used[problem_id]:
            last_used[problem_id] = day

    previous_topics: set[str] = set()
    if history:
        previous_id = max(history)[1]
        previous = next((c for c in candidates if c.problem_id == previous_id), None)
        if previous:
            previous_topics = set(previous.topics)

    def key(c: Candidate) -> tuple[date, bool, str]:
        return (
            last_used.get(c.problem_id, date.min),
            bool(previous_topics & set(c.topics)),
            c.slug,
        )

    return min(candidates, key=key)
