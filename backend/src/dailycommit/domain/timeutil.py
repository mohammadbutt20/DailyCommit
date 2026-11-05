"""All "what day is it" math. Days are local calendar dates in a given IANA timezone."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def local_day(at: datetime, tz: ZoneInfo) -> date:
    if at.tzinfo is None:
        raise ValueError("naive datetime")
    return at.astimezone(tz).date()


def day_start(day: date, tz: ZoneInfo) -> datetime:
    """The UTC instant at which local `day` begins (local midnight; DST-safe)."""
    return datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(UTC)


def day_end(day: date, tz: ZoneInfo) -> datetime:
    return day_start(day + timedelta(days=1), tz)


def week_start(day: date) -> date:
    """Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def days_between(first: date, last: date) -> list[date]:
    """Inclusive range; empty if first > last."""
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]
