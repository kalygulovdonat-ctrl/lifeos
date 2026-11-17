"""Read side of time tracking (SDD §4.9, §5.2, §5.5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.time_tracking.models import ACTIVE, EntryStatus, TimeEntry
from common.exceptions import NotFoundError
from common.time import now


def active_timer(user: User) -> TimeEntry | None:
    return (
        TimeEntry.objects.filter(user=user, status__in=ACTIVE)
        .select_related("task", "event", "category")
        .prefetch_related("pauses")
        .first()
    )


def elapsed_seconds(entry: TimeEntry, at: datetime | None = None) -> int:
    """Live duration, derived only from server state (BR-056)."""
    if entry.status == EntryStatus.STOPPED:
        return entry.duration_seconds or 0
    moment = at or now()
    open_pause = next((p for p in entry.pauses.all() if p.resumed_at is None), None)
    end = open_pause.paused_at if open_pause else moment
    return max(0, int((end - entry.started_at).total_seconds()) - entry.paused_seconds)


def entry_get(user: User, entry_id: UUID | str) -> TimeEntry:
    try:
        return TimeEntry.objects.select_related("task", "category").get(user=user, id=entry_id)
    except (TimeEntry.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def entries_in_range(
    user: User,
    start: datetime,
    end: datetime,
    *,
    task_id: UUID | None = None,
    category_id: UUID | None = None,
) -> QuerySet[TimeEntry]:
    qs = TimeEntry.objects.filter(
        user=user, status=EntryStatus.STOPPED, started_at__lt=end, ended_at__gt=start
    )
    if task_id:
        qs = qs.filter(task_id=task_id)
    if category_id:
        qs = qs.filter(category_id=category_id)
    return qs.select_related("task", "category").order_by("-started_at")


def task_entries(user: User, task_id: UUID) -> QuerySet[TimeEntry]:
    return TimeEntry.objects.filter(user=user, task_id=task_id).select_related("task").order_by("-started_at")


def overlaps_for(
    user: User, start: datetime, end: datetime, *, exclude_id: UUID | None = None
) -> list[TimeEntry]:
    qs = TimeEntry.objects.filter(
        user=user, status=EntryStatus.STOPPED, started_at__lt=end, ended_at__gt=start
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return list(qs)


def merged_seconds(intervals: list[tuple[datetime, datetime]]) -> int:
    """Union length: overlapping sessions are never counted twice (SDD §4.9)."""
    total = 0
    cur_s: datetime | None = None
    cur_e: datetime | None = None
    for s, e in sorted(intervals):
        if cur_e is None or s > cur_e:
            if cur_e is not None and cur_s is not None:
                total += int((cur_e - cur_s).total_seconds())
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None and cur_s is not None:
        total += int((cur_e - cur_s).total_seconds())
    return total


def tracked_seconds(user: User, start: datetime, end: datetime, *, focus_only: bool = False) -> int:
    """Tracked time inside [start, end), clipped and merged. Pauses are spread evenly (approximation)."""
    qs = entries_in_range(user, start, end)
    if focus_only:
        qs = qs.filter(Q(is_focus=True) | Q(event__time_type="FOCUS"))
    intervals = []
    for e in qs:
        s, f = max(e.started_at, start), min(e.ended_at, end)
        if f <= s:
            continue
        span = (e.ended_at - e.started_at).total_seconds() or 1
        ratio = (e.duration_seconds or 0) / span
        intervals.append((s, s + timedelta(seconds=(f - s).total_seconds() * ratio)))
    return merged_seconds(intervals)


@dataclass
class PlanVsActual:
    planned_minutes: int
    matched_minutes: int
    actual_minutes: int
    unplanned_minutes: int
    accuracy: float | None
    items: list[dict[str, Any]]


def plan_vs_actual(user: User, start: datetime, end: datetime) -> PlanVsActual:
    """Schedule accuracy (SDD §5.5): planned blocks that already ended vs tracked time."""
    from apps.schedule.selectors import events_in_range

    moment = now()
    events = [
        e
        for e in events_in_range(user, start, end, include_cancelled=False)
        if e.time_type in ("FOCUS", "PERSONAL", "FIXED")
        and e.start_at >= start
        and e.end_at <= min(end, moment)
    ]
    entries = list(entries_in_range(user, start, end))
    planned = matched = 0
    used: list[tuple[datetime, datetime]] = []
    items = []
    for ev in events:
        duration = int((ev.end_at - ev.start_at).total_seconds())
        related = [
            x
            for x in entries
            if (ev.id is not None and x.event_id == ev.id)
            or (ev.task_id is not None and x.task_id == ev.task_id)
        ]
        overlap = merged_seconds(
            [
                (max(x.started_at, ev.start_at), min(x.ended_at, ev.end_at))
                for x in related
                if x.started_at < ev.end_at and x.ended_at > ev.start_at
            ]
        )
        overlap = min(overlap, duration)
        used.extend((max(x.started_at, ev.start_at), min(x.ended_at, ev.end_at)) for x in related)
        planned += duration
        matched += overlap
        items.append({"event": ev, "planned_seconds": duration, "actual_seconds": overlap})
    actual = merged_seconds([(max(x.started_at, start), min(x.ended_at, end)) for x in entries])
    unplanned = max(0, actual - merged_seconds([(s, e) for s, e in used if e > s]))
    return PlanVsActual(
        planned_minutes=planned // 60,
        matched_minutes=matched // 60,
        actual_minutes=actual // 60,
        unplanned_minutes=unplanned // 60,
        accuracy=(matched / planned) if planned else None,
        items=items,
    )
