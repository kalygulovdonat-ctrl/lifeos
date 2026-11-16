"""Single source of truth for time handling (SDD §2).

Business code must not call date.today() / datetime.now() directly — use these helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, available_timezones

from django.utils import timezone as dj_timezone

Period = Literal["day", "week", "month"]


@lru_cache(maxsize=1)
def _all_timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_valid_timezone(name: str) -> bool:
    return name in _all_timezones()


def now() -> datetime:
    """Current aware UTC datetime."""
    return dj_timezone.now()


def local_now(tz_name: str) -> datetime:
    return now().astimezone(ZoneInfo(tz_name))


def local_today(tz_name: str) -> date:
    return local_now(tz_name).date()


def local_date_of(moment: datetime, tz_name: str) -> date:
    if dj_timezone.is_naive(moment):
        raise ValueError("Naive datetimes are not allowed")
    return moment.astimezone(ZoneInfo(tz_name)).date()


@dataclass(frozen=True)
class PeriodBounds:
    """Half-open interval [start, end) in UTC plus the local dates it covers."""

    start: datetime
    end: datetime
    first_day: date
    last_day: date


def _local_midnight(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz)


def period_bounds(tz_name: str, period: Period, anchor: date, week_start: int = 1) -> PeriodBounds:
    """Bounds of the day/week/month containing `anchor` in the user's time zone.

    week_start is ISO weekday (1 = Monday … 7 = Sunday).
    Correct across DST: a local day may be 23 or 25 hours long.
    """
    if not 1 <= week_start <= 7:
        raise ValueError("week_start must be 1..7")
    tz = ZoneInfo(tz_name)

    if period == "day":
        first = last = anchor
    elif period == "week":
        offset = (anchor.isoweekday() - week_start) % 7
        first = anchor - timedelta(days=offset)
        last = first + timedelta(days=6)
    elif period == "month":
        first = anchor.replace(day=1)
        next_month = (first + timedelta(days=32)).replace(day=1)
        last = next_month - timedelta(days=1)
    else:  # pragma: no cover
        raise ValueError(f"Unknown period: {period}")

    start = _local_midnight(first, tz).astimezone(ZoneInfo("UTC"))
    end = _local_midnight(last + timedelta(days=1), tz).astimezone(ZoneInfo("UTC"))
    return PeriodBounds(start=start, end=end, first_day=first, last_day=last)


def intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Half-open [start, end) overlap: touching intervals do not overlap (SDD §2.7)."""
    return a_start < b_end and b_start < a_end
