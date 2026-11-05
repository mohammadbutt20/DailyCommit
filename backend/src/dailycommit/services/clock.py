from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

from dailycommit.domain import timeutil
from dailycommit.models import Group, utcnow


@lru_cache(maxsize=512)
def _zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def group_tz(group: Group) -> ZoneInfo:
    """The timezone that defines a group's day. The only place that decides it."""
    return _zone(group.timezone)


def today(group: Group, now: datetime | None = None) -> date:
    return timeutil.local_day(now or utcnow(), group_tz(group))


@lru_cache(maxsize=1)
def valid_timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_valid_timezone(name: str) -> bool:
    return name in valid_timezones()
