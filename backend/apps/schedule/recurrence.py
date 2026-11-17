"""RRULE handling (SDD §4.4, ADR-007).

The API speaks a small structured recurrence; the database stores the RFC 5545 string.
Expansion happens in the series' own time zone on naive wall-clock times, so "every Monday
at 09:00" stays 09:00 local across DST changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

from common.exceptions import DomainValidationError

FREQS = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")
WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
MAX_OCCURRENCES = 1000
UTC = ZoneInfo("UTC")


@dataclass
class Recurrence:
    freq: str
    interval: int = 1
    by_day: list[str] = field(default_factory=list)
    by_month_day: list[int] = field(default_factory=list)
    count: int | None = None
    until: date | None = None

    def to_rrule(self) -> str:
        if self.freq not in FREQS:
            raise DomainValidationError(details={"recurrence": [f"freq must be one of {', '.join(FREQS)}."]})
        if not 1 <= self.interval <= 366:
            raise DomainValidationError(details={"recurrence": ["interval must be 1..366."]})
        if any(d not in WEEKDAYS for d in self.by_day):
            raise DomainValidationError(details={"recurrence": ["by_day accepts MO..SU."]})
        if any(not (1 <= d <= 31 or -31 <= d <= -1) for d in self.by_month_day):
            raise DomainValidationError(details={"recurrence": ["by_month_day accepts 1..31 or -31..-1."]})
        if self.count is not None and not 1 <= self.count <= MAX_OCCURRENCES:
            raise DomainValidationError(details={"recurrence": [f"count must be 1..{MAX_OCCURRENCES}."]})
        if self.count is not None and self.until is not None:
            raise DomainValidationError(details={"recurrence": ["Use either count or until, not both."]})

        parts = [f"FREQ={self.freq}"]
        if self.interval != 1:
            parts.append(f"INTERVAL={self.interval}")
        if self.by_day:
            parts.append("BYDAY=" + ",".join(sorted(set(self.by_day), key=WEEKDAYS.index)))
        if self.by_month_day:
            parts.append("BYMONTHDAY=" + ",".join(str(d) for d in sorted(set(self.by_month_day))))
        if self.count is not None:
            parts.append(f"COUNT={self.count}")
        if self.until is not None:
            parts.append(f"UNTIL={self.until:%Y%m%d}T235959")
        return ";".join(parts)

    @classmethod
    def from_rrule(cls, rule: str) -> Recurrence:
        parts = dict(p.split("=", 1) for p in rule.split(";") if "=" in p)
        until = parts.get("UNTIL")
        return cls(
            freq=parts["FREQ"],
            interval=int(parts.get("INTERVAL", "1")),
            by_day=[d for d in parts.get("BYDAY", "").split(",") if d],
            by_month_day=[int(d) for d in parts.get("BYMONTHDAY", "").split(",") if d],
            count=int(parts["COUNT"]) if "COUNT" in parts else None,
            until=datetime.strptime(until[:8], "%Y%m%d").date() if until else None,  # noqa: DTZ007
        )

    def until_at(self, tz_name: str) -> datetime | None:
        """End of the UNTIL day in the series' time zone, as UTC (denormalised for queries)."""
        if self.until is None:
            return None
        return datetime.combine(
            self.until + timedelta(days=1), time.min, tzinfo=ZoneInfo(tz_name)
        ).astimezone(UTC)


def _local_naive(moment: datetime, tz: ZoneInfo) -> datetime:
    return moment.astimezone(tz).replace(tzinfo=None)


def expand(
    *,
    rule: str,
    dtstart_at: datetime,
    tz_name: str,
    duration: timedelta,
    window_start: datetime,
    window_end: datetime,
    limit: int = MAX_OCCURRENCES,
) -> list[datetime]:
    """UTC start times of occurrences overlapping [window_start, window_end)."""
    tz = ZoneInfo(tz_name)
    local_start = _local_naive(dtstart_at, tz)
    parsed = rrulestr(rule, dtstart=local_start)
    lo = _local_naive(window_start - duration, tz) - timedelta(hours=1)  # DST slack
    hi = _local_naive(window_end, tz) + timedelta(hours=1)
    result: list[datetime] = []
    for local in parsed.xafter(lo, inc=True):
        if local > hi or len(result) >= limit:
            break
        start = local.replace(tzinfo=tz).astimezone(UTC)
        if start < window_end and start + duration > window_start:
            result.append(start)
    return result


def is_occurrence(*, rule: str, dtstart_at: datetime, tz_name: str, moment: datetime) -> bool:
    tz = ZoneInfo(tz_name)
    parsed = rrulestr(rule, dtstart=_local_naive(dtstart_at, tz))
    local = _local_naive(moment, tz)
    return any(
        occ.replace(tzinfo=tz).astimezone(UTC) == moment.astimezone(UTC)
        for occ in parsed.between(local - timedelta(hours=2), local + timedelta(hours=2), inc=True)
    )


def occurrences_before(*, rule: str, dtstart_at: datetime, tz_name: str, moment: datetime) -> int:
    tz = ZoneInfo(tz_name)
    parsed = rrulestr(rule, dtstart=_local_naive(dtstart_at, tz))
    return len(parsed.between(_local_naive(dtstart_at, tz), _local_naive(moment, tz), inc=False)) + 1


def truncate_before(rule: str, moment: datetime, tz_name: str) -> str:
    """Rule ending right before `moment` (for "this and following" edits)."""
    tz = ZoneInfo(tz_name)
    last = _local_naive(moment, tz) - timedelta(seconds=1)
    parts = [p for p in rule.split(";") if not p.startswith(("UNTIL=", "COUNT="))]
    parts.append(f"UNTIL={last:%Y%m%dT%H%M%S}")
    return ";".join(parts)
