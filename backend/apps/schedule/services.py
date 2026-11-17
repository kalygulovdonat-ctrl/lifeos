"""Write side of the schedule (SDD §4.4, §6.2, §6.3)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.accounts.models import Category, User
from apps.schedule.models import Event, EventReschedule, EventSeries, EventSeriesExdate, EventStatus
from apps.schedule.recurrence import Recurrence, expand, is_occurrence, occurrences_before, truncate_before
from apps.schedule.selectors import (
    CONFLICT,
    INFO,
    EventView,
    Overlap,
    conflicts_for,
    view_of_event,
    view_of_occurrence,
)
from apps.tasks.models import Task
from common.audit import audit, diff
from common.exceptions import ConflictError, DomainValidationError, NotFoundError
from common.time import is_valid_timezone, now

TEMPLATE_FIELDS = {
    "title",
    "description",
    "location",
    "color",
    "category",
    "time_type",
    "task",
    "reminder_minutes",
    "timezone",
    "all_day",
}
EVENT_FIELDS = TEMPLATE_FIELDS | {"start_at", "end_at"}
# How far ahead a new series is checked for conflicts.
SERIES_CHECK_HORIZON = timedelta(weeks=8)


# ---------------------------------------------------------------- validation & conflicts


def _validate(user: User, data: dict[str, Any], start: datetime, end: datetime) -> None:
    if end <= start:
        raise DomainValidationError(details={"end_at": ["Must be later than start_at (BR-011)."]})
    if "title" in data and not str(data["title"]).strip():
        raise DomainValidationError(details={"title": ["Title must not be blank."]})
    category: Category | None = data.get("category")
    if category is not None and category.user_id != user.id:
        raise DomainValidationError(details={"category_id": ["Unknown category."]})
    task: Task | None = data.get("task")
    if task is not None and task.user_id != user.id:
        raise DomainValidationError(details={"task_id": ["Unknown task."]})
    if "timezone" in data and not is_valid_timezone(data["timezone"]):
        raise DomainValidationError(details={"timezone": ["Unknown time zone."]})


def brief(v: EventView) -> dict[str, Any]:
    return {
        "id": str(v.id) if v.id else None,
        "occurrence_key": v.occurrence_key,
        "title": v.title,
        "start_at": v.start_at.isoformat(),
        "end_at": v.end_at.isoformat(),
        "time_type": v.time_type,
    }


def _warnings(overlaps: list[Overlap], *, force: bool) -> list[dict[str, Any]]:
    """CONFLICT → 409 unless forced (BR-013); WARNING (and forced CONFLICT) → warnings[]."""
    hard = [o for o in overlaps if o.severity == CONFLICT]
    if hard and not force:
        raise ConflictError(
            "The time overlaps a fixed event.",
            code="SCHEDULE_CONFLICT",
            details={"conflicting": [brief(o.other) for o in hard]},
        )
    warnings = []
    for level in (CONFLICT, "WARNING"):
        items = [o.other for o in overlaps if o.severity == level]
        if items:
            warnings.append(
                {"code": "SCHEDULE_OVERLAP", "severity": level, "conflicting": [brief(v) for v in items]}
            )
    return warnings


def _series_overlaps(user: User, series: EventSeries, start_from: datetime | None = None) -> list[Overlap]:
    window_start = start_from or series.dtstart_at
    duration = timedelta(minutes=series.duration_minutes)
    starts = expand(
        rule=series.rrule,
        dtstart_at=series.dtstart_at,
        tz_name=series.timezone,
        duration=duration,
        window_start=window_start,
        window_end=window_start + SERIES_CHECK_HORIZON,
        limit=100,
    )
    seen: set[str] = set()
    found: list[Overlap] = []
    for occ in starts:
        for o in conflicts_for(user, occ, occ + duration, series.time_type, exclude_series_id=series.id):
            if o.severity != INFO and o.other.key not in seen:
                seen.add(o.other.key)
                found.append(o)
    return found


def check_conflicts(
    *, user: User, start: datetime, end: datetime, time_type: str, exclude_id: UUID | None = None
) -> list[Overlap]:
    if end <= start:
        raise DomainValidationError(details={"end_at": ["Must be later than start_at (BR-011)."]})
    return conflicts_for(user, start, end, time_type, exclude_event_id=exclude_id)


# ---------------------------------------------------------------- events


@transaction.atomic
def event_create(
    *, user: User, data: dict[str, Any], recurrence: Recurrence | None = None, force: bool = False
) -> tuple[Event | EventSeries, list[dict[str, Any]]]:
    data = {k: v for k, v in data.items() if k in EVENT_FIELDS}
    data.setdefault("timezone", user.profile.timezone)
    data["title"] = str(data.get("title", "")).strip()
    start, end = data["start_at"], data["end_at"]
    _validate(user, data, start, end)

    if recurrence is not None:
        rule = recurrence.to_rrule()
        template = {k: v for k, v in data.items() if k in TEMPLATE_FIELDS}
        series = EventSeries.objects.create(
            user=user,
            dtstart_at=start,
            duration_minutes=int((end - start).total_seconds() // 60) or 1,
            rrule=rule,
            until_at=recurrence.until_at(data["timezone"]),
            **template,
        )
        warnings = _warnings(_series_overlaps(user, series), force=force)
        audit(user=user, entity_type="event_series", entity_id=series.id, action="CREATE")
        return series, warnings

    overlaps = conflicts_for(user, start, end, data.get("time_type", "PERSONAL"))
    warnings = _warnings([o for o in overlaps if o.severity != INFO], force=force)
    event = Event.objects.create(user=user, **data)
    audit(user=user, entity_type="event", entity_id=event.id, action="CREATE")
    return event, warnings


def _record_move(event: Event, old: tuple[datetime, datetime], reason: str) -> None:
    if (event.start_at, event.end_at) != old:
        EventReschedule.objects.create(
            user_id=event.user_id,
            event=event,
            old_start_at=old[0],
            old_end_at=old[1],
            new_start_at=event.start_at,
            new_end_at=event.end_at,
            reason=reason.strip(),
        )


@transaction.atomic
def event_update(
    *, user: User, event: Event, data: dict[str, Any], force: bool = False, reason: str = ""
) -> tuple[Event, list[dict[str, Any]]]:
    data = {k: v for k, v in data.items() if k in EVENT_FIELDS | {"status"}}
    start = data.get("start_at", event.start_at)
    end = data.get("end_at", event.end_at)
    _validate(user, data, start, end)
    old = (event.start_at, event.end_at)
    warnings: list[dict[str, Any]] = []
    time_type = data.get("time_type", event.time_type)
    if (start, end) != old or time_type != event.time_type:
        overlaps = conflicts_for(user, start, end, time_type, exclude_event_id=event.id)
        warnings = _warnings([o for o in overlaps if o.severity != INFO], force=force)
    changes = diff(event, data)
    for k, v in data.items():
        setattr(event, k, v.strip() if k == "title" else v)
    event.save()
    _record_move(event, old, reason)
    if changes:
        audit(user=user, entity_type="event", entity_id=event.id, action="UPDATE", changes=changes)
    return event, warnings


def event_reschedule(
    *, user: User, event: Event, start_at: datetime, end_at: datetime, reason: str = "", force: bool = False
) -> tuple[Event, list[dict[str, Any]]]:
    return event_update(
        user=user, event=event, data={"start_at": start_at, "end_at": end_at}, force=force, reason=reason
    )


def event_set_status(*, user: User, event: Event, status: str) -> Event:
    if status not in EventStatus.values:
        raise DomainValidationError(details={"status": ["Unknown status."]})
    old = event.status
    event.status = status
    event.save(update_fields=["status", "updated_at"])
    audit(
        user=user, entity_type="event", entity_id=event.id, action="STATUS", changes={"status": [old, status]}
    )
    return event


def event_delete(*, user: User, event: Event) -> None:
    """Soft delete. A deleted override keeps hiding its virtual occurrence."""
    event.deleted_at = now()
    event.save(update_fields=["deleted_at", "updated_at"])
    audit(user=user, entity_type="event", entity_id=event.id, action="DELETE")


# ---------------------------------------------------------------- series


@transaction.atomic
def series_update(
    *,
    user: User,
    series: EventSeries,
    data: dict[str, Any],
    recurrence: Recurrence | None = None,
    force: bool = False,
) -> tuple[EventSeries, list[dict[str, Any]]]:
    data = dict(data)
    start = data.pop("start_at", series.dtstart_at)
    end = data.pop("end_at", start + timedelta(minutes=series.duration_minutes))
    data = {k: v for k, v in data.items() if k in TEMPLATE_FIELDS}
    _validate(user, data, start, end)
    timing_changed = start != series.dtstart_at or recurrence is not None
    for k, v in data.items():
        setattr(series, k, v.strip() if k == "title" else v)
    series.dtstart_at = start
    series.duration_minutes = int((end - start).total_seconds() // 60) or 1
    if recurrence is not None:
        series.rrule = recurrence.to_rrule()
        series.until_at = recurrence.until_at(series.timezone)
    series.save()
    warnings: list[dict[str, Any]] = []
    if timing_changed or "time_type" in data:
        warnings = _warnings(_series_overlaps(user, series, max(start, now())), force=force)
    audit(user=user, entity_type="event_series", entity_id=series.id, action="UPDATE")
    return series, warnings


def series_delete(*, user: User, series: EventSeries) -> None:
    moment = now()
    series.deleted_at = moment
    series.is_active = False
    series.save(update_fields=["deleted_at", "is_active", "updated_at"])
    Event.objects.filter(user=user, series=series).update(deleted_at=moment)
    audit(user=user, entity_type="event_series", entity_id=series.id, action="DELETE")


def _require_occurrence(series: EventSeries, original_start: datetime) -> None:
    if not is_occurrence(
        rule=series.rrule, dtstart_at=series.dtstart_at, tz_name=series.timezone, moment=original_start
    ):
        raise NotFoundError("This series has no occurrence at that time.")


@transaction.atomic
def occurrence_edit(
    *,
    user: User,
    series: EventSeries,
    original_start: datetime,
    data: dict[str, Any],
    scope: str = "this",
    force: bool = False,
) -> tuple[Event | EventSeries, list[dict[str, Any]]]:
    """Edit one occurrence (creates/updates an override) or split the series (scope=following)."""
    _require_occurrence(series, original_start)
    duration = timedelta(minutes=series.duration_minutes)

    if scope == "following":
        return _split(user=user, series=series, original_start=original_start, data=data, force=force)

    override = Event.all_objects.filter(user=user, series=series, original_start_at=original_start).first()
    if override is None:
        template = {k: getattr(series, k) for k in TEMPLATE_FIELDS}
        override = Event.objects.create(
            user=user,
            series=series,
            original_start_at=original_start,
            start_at=original_start,
            end_at=original_start + duration,
            **template,
        )
    elif override.deleted_at is not None:
        raise NotFoundError("This occurrence was deleted.")
    return event_update(user=user, event=override, data=data, force=force)


def _split(
    *, user: User, series: EventSeries, original_start: datetime, data: dict[str, Any], force: bool
) -> tuple[EventSeries, list[dict[str, Any]]]:
    old_rule = Recurrence.from_rrule(series.rrule)
    if original_start == series.dtstart_at:
        recurrence = None if "recurrence" not in data else data.pop("recurrence")
        return series_update(user=user, series=series, data=data, recurrence=recurrence, force=force)

    new_recurrence: Recurrence = data.pop("recurrence", None) or Recurrence(
        freq=old_rule.freq,
        interval=old_rule.interval,
        by_day=old_rule.by_day,
        by_month_day=old_rule.by_month_day,
        until=old_rule.until,
        count=(
            old_rule.count
            - occurrences_before(
                rule=series.rrule,
                dtstart_at=series.dtstart_at,
                tz_name=series.timezone,
                moment=original_start,
            )
            if old_rule.count
            else None
        ),
    )
    series.rrule = truncate_before(series.rrule, original_start, series.timezone)
    series.until_at = original_start
    series.save(update_fields=["rrule", "until_at", "updated_at"])

    duration = timedelta(minutes=series.duration_minutes)
    start = data.get("start_at", original_start)
    template = {k: getattr(series, k) for k in TEMPLATE_FIELDS}
    template.update({k: v for k, v in data.items() if k in TEMPLATE_FIELDS})
    template["start_at"] = start
    template["end_at"] = data.get("end_at", start + duration)
    created, warnings = event_create(user=user, data=template, recurrence=new_recurrence, force=force)
    # Overrides after the split point stay as they are (the user edited them explicitly).
    return created, warnings  # type: ignore[return-value]


def occurrence_cancel(*, user: User, series: EventSeries, original_start: datetime) -> None:
    """Exclude one occurrence (SCH-017, BR-016)."""
    _require_occurrence(series, original_start)
    EventSeriesExdate.objects.get_or_create(user=user, series=series, original_start_at=original_start)
    Event.objects.filter(user=user, series=series, original_start_at=original_start).update(deleted_at=now())
    audit(
        user=user,
        entity_type="event_series",
        entity_id=series.id,
        action="EXDATE",
        changes={"original_start_at": original_start.isoformat()},
    )


def view_for(obj: Event | EventSeries) -> EventView:
    if isinstance(obj, Event):
        return view_of_event(obj)
    return view_of_occurrence(obj, obj.dtstart_at)
