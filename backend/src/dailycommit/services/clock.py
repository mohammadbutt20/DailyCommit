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


# The zones offered when creating a group, in the order shown. A group stores the real IANA
# zone, so daylight saving follows the zone's rules; the label is only for display.
FRIENDLY_ZONES: tuple[tuple[str, str], ...] = (
    ("America/New_York", "Eastern (ET)"),
    ("America/Chicago", "Central (CT)"),
    ("America/Denver", "Mountain (MT)"),
    ("America/Phoenix", "Arizona"),
    ("America/Los_Angeles", "Pacific (PT)"),
    ("America/Anchorage", "Alaska"),
    ("Pacific/Honolulu", "Hawaii"),
)
_LABELS = dict(FRIENDLY_ZONES)


def zone_label(name: str) -> str:
    """'America/New_York' -> 'Eastern (ET)'. A zone outside the list (groups may have been
    created with any IANA zone) gets its city: 'Europe/London' -> 'London', 'UTC' -> 'UTC'."""
    if name in _LABELS:
        return _LABELS[name]
    return name.rsplit("/", 1)[-1].replace("_", " ")
