from datetime import date, datetime
from zoneinfo import ZoneInfo

from dailycommit.config import settings
from dailycommit.domain import timeutil
from dailycommit.models import utcnow


def group_tz(group_id: int | None = None) -> ZoneInfo:
    """The timezone that defines a group's day. Single app-wide zone for now; per-group zones
    are a later slice and only need to change this function (plus a column)."""
    return settings.day_tz


def today(group_id: int | None = None, now: datetime | None = None) -> date:
    return timeutil.local_day(now or utcnow(), group_tz(group_id))
