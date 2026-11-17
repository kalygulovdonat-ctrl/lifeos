"""Read side of the schedule (SDD §6.2, §6.3, §5.8). Every function takes the owner first."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.schedule.models import Event, EventSeries, EventSeriesExdate, EventStatus, TimeType
from apps.schedule.recurrence import MAX_OCCURRENCES, Recurrence, expand
from common.exceptions import NotFoundError
from common.time import period_bounds


@dataclass
class EventView:
    """One item of the calendar: a stored event or a virtual occurrence of a series."""

    id: UUID | None
    series_id: UUID | None
    original_start_at: datetime | None
    title: str
    description: str
    location: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    timezone: str
    time_type: str
    status: str
    category_id: UUID | None
    color: str | None
    task_id: UUID | None
    task_title: str | None
    reminder_minutes: int | None
    recurrence: Recurrence | None = None

    @property
    def occurrence_key(self) -> str | None:
        if self.series_id is None or self.original_start_at is None:
            return None
        return f"{self.series_id}:{int(self.original_start_at.timestamp())}"

    @property
    def key(self) -> str:
        return str(self.id) if self.id else str(self.occurrence_key)

    @property
    def minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60)


def _task_title(obj: Any) -> str | None:
    task = getattr(obj, "task", None)
    return task.title if task is not None and task.deleted_at is None else None


def view_of_event(event: Event, series: EventSeries | None = None) -> EventView:
    series = series or (event.series if event.series_id else None)
    return EventView(
        id=event.id,
        series_id=event.series_id,
        original_start_at=event.original_start_at,
        title=event.title,
        description=event.description,
        location=event.location,
        start_at=event.start_at,
        end_at=event.end_at,
        all_day=event.all_day,
        timezone=event.timezone,
        time_type=event.time_type,
        status=event.status,
        category_id=event.category_id,
        color=event.color,
        task_id=event.task_id,
        task_title=_task_title(event),
        reminder_minutes=event.reminder_minutes,
        recurrence=Recurrence.from_rrule(series.rrule) if series is not None else None,
    )


def view_of_occurrence(series: EventSeries, start: datetime) -> EventView:
    return EventView(
        id=None,
        series_id=series.id,
        original_start_at=start,
        title=series.title,
        description=series.description,
        location=series.location,
        start_at=start,
        end_at=start + timedelta(minutes=series.duration_minutes),
        all_day=series.all_day,
        timezone=series.timezone,
        time_type=series.time_type,
        status=EventStatus.PLANNED,
        category_id=series.category_id,
        color=series.color,
        task_id=series.task_id,
        task_title=_task_title(series),
        reminder_minutes=series.reminder_minutes,
        recurrence=Recurrence.from_rrule(series.rrule),
    )


def event_get(user: User, event_id: UUID | str) -> Event:
    try:
        return Event.objects.select_related("task", "series").get(user=user, id=event_id)
    except (Event.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def series_get(user: User, series_id: UUID | str) -> EventSeries:
    try:
        return EventSeries.objects.select_related("task").get(user=user, id=series_id)
    except (EventSeries.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def series_list(user: User) -> QuerySet[EventSeries]:
    return EventSeries.objects.filter(user=user)


def events_in_range(
    user: User,
    start: datetime,
    end: datetime,
    *,
    time_types: list[str] | None = None,
    category_id: UUID | str | None = None,
    include_cancelled: bool = True,
) -> list[EventView]:
    """Stored events plus series occurrences expanded in [start, end), sorted by start."""
    events = Event.objects.filter(user=user, start_at__lt=end, end_at__gt=start).select_related(
        "task", "series"
    )
    series_qs = (
        EventSeries.objects.filter(user=user, dtstart_at__lt=end)
        .filter(Q(until_at__isnull=True) | Q(until_at__gt=start))
        .select_related("task")
    )
    if time_types:
        events = events.filter(time_type__in=time_types)
        series_qs = series_qs.filter(time_type__in=time_types)
    if category_id:
        events = events.filter(category_id=category_id)
        series_qs = series_qs.filter(category_id=category_id)
    if not include_cancelled:
        events = events.exclude(status=EventStatus.CANCELLED)

    items = [view_of_event(e) for e in events]
    series_list_ = list(series_qs)
    if series_list_:
        ids = [s.id for s in series_list_]
        # Every override (even a deleted one) replaces its virtual occurrence.
        replaced = set(
            Event.all_objects.filter(user=user, series_id__in=ids).values_list(
                "series_id", "original_start_at"
            )
        )
        excluded = set(
            EventSeriesExdate.objects.filter(user=user, series_id__in=ids).values_list(
                "series_id", "original_start_at"
            )
        )
        budget = MAX_OCCURRENCES
        for series in series_list_:
            starts = expand(
                rule=series.rrule,
                dtstart_at=series.dtstart_at,
                tz_name=series.timezone,
                duration=timedelta(minutes=series.duration_minutes),
                window_start=start,
                window_end=end,
                limit=budget,
            )
            budget -= len(starts)
            for occ in starts:
                if (series.id, occ) in replaced or (series.id, occ) in excluded:
                    continue
                items.append(view_of_occurrence(series, occ))
            if budget <= 0:
                break
    items.sort(key=lambda v: (v.start_at, v.end_at, v.title))
    return items


def local_range(user: User, first: date, last: date) -> tuple[datetime, datetime]:
    profile = user.profile
    start = period_bounds(profile.timezone, "day", first).start
    end = period_bounds(profile.timezone, "day", last).end
    return start, end


# ---------------------------------------------------------------- conflicts (§6.3)

CONFLICT, WARNING, INFO = "CONFLICT", "WARNING", "INFO"
_PERSONALISH = {TimeType.FOCUS, TimeType.PERSONAL}


def severity(new: str, existing: str) -> str:
    if new in (TimeType.BUFFER, TimeType.FREE):
        return INFO
    if new == TimeType.FIXED:
        if existing == TimeType.FIXED:
            return CONFLICT
        return INFO if existing == TimeType.BUFFER else WARNING
    if new in _PERSONALISH:
        return INFO if existing in (TimeType.BUFFER, TimeType.FREE) else WARNING
    # REST
    return WARNING if existing in (TimeType.FIXED, *_PERSONALISH) else INFO


@dataclass
class Overlap:
    severity: str
    other: EventView


def conflicts_for(
    user: User,
    start: datetime,
    end: datetime,
    time_type: str,
    *,
    exclude_event_id: UUID | None = None,
    exclude_series_id: UUID | None = None,
    exclude_occurrence: tuple[UUID, datetime] | None = None,
) -> list[Overlap]:
    found: list[Overlap] = []
    for other in events_in_range(user, start, end, include_cancelled=False):
        if exclude_event_id and other.id == exclude_event_id:
            continue
        if exclude_series_id and other.series_id == exclude_series_id and other.id is None:
            continue
        if exclude_occurrence and (other.series_id, other.original_start_at) == exclude_occurrence:
            continue
        found.append(Overlap(severity(time_type, other.time_type), other))
    return found


def conflicts_in_range(user: User, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """All overlapping pairs in the window (GET /events/conflicts/)."""
    items = events_in_range(user, start, end, include_cancelled=False)
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if b.start_at >= a.end_at:
                break
            level = max(
                severity(a.time_type, b.time_type),
                severity(b.time_type, a.time_type),
                key=[INFO, WARNING, CONFLICT].index,
            )
            pairs.append({"severity": level, "a": a, "b": b})
    return pairs


# ---------------------------------------------------------------- free time (§5.8)


@dataclass
class FreeTime:
    window_start: datetime
    window_end: datetime
    slots: list[tuple[datetime, datetime]]
    busy_minutes: int
    free_minutes: int
    reserved_free_minutes: int


def _merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for s, e in sorted(intervals):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def free_time(user: User, day: date, *, min_minutes: int = 15) -> FreeTime:
    profile = user.profile
    tz = ZoneInfo(profile.timezone)
    window_start = datetime.combine(day, profile.day_start_time, tzinfo=tz).astimezone(ZoneInfo("UTC"))
    window_end = datetime.combine(day, profile.day_end_time, tzinfo=tz).astimezone(ZoneInfo("UTC"))
    items = events_in_range(user, window_start, window_end, include_cancelled=False)

    def clip(v: EventView) -> tuple[datetime, datetime]:
        return max(v.start_at, window_start), min(v.end_at, window_end)

    busy = _merge([clip(v) for v in items if v.time_type != TimeType.FREE])
    reserved = _merge([clip(v) for v in items if v.time_type == TimeType.FREE])

    slots: list[tuple[datetime, datetime]] = []
    cursor = window_start
    for s, e in busy:
        if s > cursor:
            slots.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < window_end:
        slots.append((cursor, window_end))

    def minutes(intervals: list[tuple[datetime, datetime]]) -> int:
        return int(sum((e - s).total_seconds() for s, e in intervals) // 60)

    slots = [(s, e) for s, e in slots if (e - s) >= timedelta(minutes=min_minutes)]
    return FreeTime(
        window_start=window_start,
        window_end=window_end,
        slots=slots,
        busy_minutes=minutes(busy),
        free_minutes=minutes(slots),
        reserved_free_minutes=minutes(reserved),
    )
