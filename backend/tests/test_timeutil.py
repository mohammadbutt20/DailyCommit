from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from dailycommit.domain.timeutil import day_end, day_start, days_between, local_day, week_start

NY = ZoneInfo("America/New_York")


def test_local_day_uses_timezone_not_utc():
    # 02:30 UTC on the 21st is still the evening of the 20th in New York.
    assert local_day(datetime(2026, 10, 21, 2, 30, tzinfo=UTC), NY) == date(2026, 10, 20)


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError):
        local_day(datetime(2026, 10, 21), NY)


def test_day_start_is_local_midnight_in_utc():
    assert day_start(date(2026, 10, 20), NY) == datetime(2026, 10, 20, 4, 0, tzinfo=UTC)


def test_dst_fall_back_day_is_25_hours():
    # US DST ends Sunday 2026-11-01.
    d = date(2026, 11, 1)
    assert (day_end(d, NY) - day_start(d, NY)).total_seconds() == 25 * 3600


def test_dst_spring_forward_day_is_23_hours():
    d = date(2026, 3, 8)
    assert (day_end(d, NY) - day_start(d, NY)).total_seconds() == 23 * 3600


def test_week_start_is_monday():
    assert week_start(date(2026, 10, 22)) == date(2026, 10, 19)  # Thursday -> Monday
    assert week_start(date(2026, 10, 19)) == date(2026, 10, 19)
    assert week_start(date(2026, 10, 25)) == date(2026, 10, 19)  # Sunday


def test_days_between_inclusive_and_empty():
    assert days_between(date(2026, 1, 30), date(2026, 2, 1)) == [
        date(2026, 1, 30),
        date(2026, 1, 31),
        date(2026, 2, 1),
    ]
    assert days_between(date(2026, 2, 2), date(2026, 2, 1)) == []
