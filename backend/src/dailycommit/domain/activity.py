"""A group's activity feed: solves and joins, newest first.

The same event can reach the browser twice: once in the history it loads on page open and
once live over the WebSocket. Both carry the id built here, so the browser can drop
duplicates. An id names the underlying row, not the message: a solve is unique per
(group, day, user) and a membership per (group, user).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

ActivityKind = Literal["solve", "join"]


def solve_id(day: date, user_id: int) -> str:
    return f"solve:{day.isoformat()}:{user_id}"


def join_id(user_id: int) -> str:
    return f"join:{user_id}"


@dataclass(frozen=True)
class Activity:
    id: str
    kind: ActivityKind
    user_id: int
    display_name: str
    at: datetime
    problem_slug: str | None = None  # solves only


def recent_activity(items: Iterable[Activity], limit: int) -> list[Activity]:
    """The `limit` newest distinct events. Ties on `at` break by id, so the order is stable."""
    unique = {a.id: a for a in items}
    ordered = sorted(unique.values(), key=lambda a: (a.at, a.id), reverse=True)
    return ordered[: max(limit, 0)]
