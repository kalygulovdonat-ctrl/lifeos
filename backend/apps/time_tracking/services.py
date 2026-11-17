"""Write side of time tracking (SDD §4.9, BR-050…BR-056)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction

from apps.accounts.models import Category, User
from apps.time_tracking.models import (
    ACTIVE,
    EntrySource,
    EntryStatus,
    TimeEntry,
    TimeEntryPause,
    TimeEntryRevision,
)
from apps.time_tracking.selectors import overlaps_for
from common.audit import audit
from common.exceptions import ConflictError, DomainValidationError
from common.time import now

FUTURE_TOLERANCE = timedelta(minutes=5)
MAX_MANUAL = timedelta(hours=24)
DUPLICATE_TOLERANCE = timedelta(seconds=60)
LINK_FIELDS = {"task", "event", "category", "description", "is_focus"}


def _invalid(field: str, message: str) -> DomainValidationError:
    return DomainValidationError(details={field: [message]})


def _check_links(user: User, data: dict[str, Any]) -> None:
    for field in ("task", "event", "category"):
        obj = data.get(field)
        if obj is not None and obj.user_id != user.id:
            raise _invalid(f"{field}_id", f"Unknown {field}.")
    category: Category | None = data.get("category")
    task = data.get("task")
    if category is None and task is not None and task.category_id:
        data["category"] = task.category  # TIME-006: inherit the task's category


def _no_active_timer() -> ConflictError:
    return ConflictError("No timer is running.", code="NO_ACTIVE_TIMER")


def _active(user: User) -> TimeEntry:
    entry = TimeEntry.objects.select_for_update().filter(user=user, status__in=ACTIVE).first()
    if entry is None:
        raise _no_active_timer()
    return entry


@transaction.atomic
def timer_start(*, user: User, data: dict[str, Any], source: str = EntrySource.TIMER) -> TimeEntry:
    data = {k: v for k, v in data.items() if k in LINK_FIELDS}
    _check_links(user, data)
    if data.get("event") is not None and data["event"].time_type == "FOCUS":
        data.setdefault("is_focus", True)
    if TimeEntry.objects.filter(user=user, status__in=ACTIVE).exists():
        raise ConflictError("A timer is already running (BR-050).", code="TIMER_ALREADY_RUNNING")
    try:
        with transaction.atomic():
            entry = TimeEntry.objects.create(
                user=user, status=EntryStatus.RUNNING, source=source, started_at=now(), **data
            )
    except IntegrityError as exc:  # concurrent start
        raise ConflictError("A timer is already running (BR-050).", code="TIMER_ALREADY_RUNNING") from exc
    audit(user=user, entity_type="time_entry", entity_id=entry.id, action="TIMER_START")
    return entry


@transaction.atomic
def timer_pause(*, user: User) -> TimeEntry:
    entry = _active(user)
    if entry.status == EntryStatus.PAUSED:
        return entry
    TimeEntryPause.objects.create(user=user, time_entry=entry, paused_at=now())
    entry.status = EntryStatus.PAUSED
    entry.save(update_fields=["status", "updated_at"])
    return entry


def _close_pause(entry: TimeEntry, at: datetime) -> None:
    pause = TimeEntryPause.objects.filter(time_entry=entry, resumed_at__isnull=True).first()
    if pause is None:
        return
    resumed = max(at, pause.paused_at + timedelta(microseconds=1))
    pause.resumed_at = resumed
    pause.save(update_fields=["resumed_at", "updated_at"])
    entry.paused_seconds += int((resumed - pause.paused_at).total_seconds())


@transaction.atomic
def timer_resume(*, user: User) -> TimeEntry:
    entry = _active(user)
    if entry.status == EntryStatus.RUNNING:
        return entry
    _close_pause(entry, now())
    entry.status = EntryStatus.RUNNING
    entry.save(update_fields=["status", "paused_seconds", "updated_at"])
    return entry


def _duration(entry: TimeEntry) -> int:
    assert entry.ended_at is not None
    return max(0, int((entry.ended_at - entry.started_at).total_seconds()) - entry.paused_seconds)


@transaction.atomic
def timer_stop(*, user: User) -> tuple[TimeEntry, list[dict[str, Any]]]:
    entry = _active(user)
    moment = now()
    _close_pause(entry, moment)
    entry.ended_at = max(moment, entry.started_at + timedelta(seconds=1))
    entry.status = EntryStatus.STOPPED
    entry.duration_seconds = _duration(entry)
    entry.save()
    audit(user=user, entity_type="time_entry", entity_id=entry.id, action="TIMER_STOP")
    return entry, _overlap_warnings(user, entry)


@transaction.atomic
def timer_discard(*, user: User) -> None:
    entry = _active(user)
    entry.deleted_at = now()
    entry.save(update_fields=["deleted_at", "updated_at"])
    audit(user=user, entity_type="time_entry", entity_id=entry.id, action="TIMER_DISCARD")


def _overlap_warnings(user: User, entry: TimeEntry) -> list[dict[str, Any]]:
    assert entry.ended_at is not None
    others = overlaps_for(user, entry.started_at, entry.ended_at, exclude_id=entry.id)
    if not others:
        return []
    return [{"code": "TIME_ENTRY_OVERLAP", "ids": [str(o.id) for o in others]}]


def _validate_manual(user: User, start: datetime, end: datetime, task: Any, exclude: Any = None) -> None:
    if end <= start:
        raise _invalid("ended_at", "Must be later than started_at (BR-051).")
    if end > now() + FUTURE_TOLERANCE:
        raise _invalid("ended_at", "A manual entry cannot end in the future.")
    if end - start > MAX_MANUAL:
        raise _invalid("ended_at", "A single entry is limited to 24 hours.")
    for other in overlaps_for(
        user, start - DUPLICATE_TOLERANCE, end + DUPLICATE_TOLERANCE, exclude_id=exclude
    ):
        assert other.ended_at is not None
        if (
            abs(other.started_at - start) <= DUPLICATE_TOLERANCE
            and abs(other.ended_at - end) <= DUPLICATE_TOLERANCE
            and other.task_id == (task.id if task else None)
        ):
            raise ConflictError("The same session is already recorded (BR-055).", code="DUPLICATE_TIME_ENTRY")


@transaction.atomic
def entry_create_manual(
    *, user: User, started_at: datetime, ended_at: datetime, data: dict[str, Any]
) -> tuple[TimeEntry, list[dict[str, Any]]]:
    data = {k: v for k, v in data.items() if k in LINK_FIELDS}
    _check_links(user, data)
    _validate_manual(user, started_at, ended_at, data.get("task"))
    entry = TimeEntry(
        user=user,
        status=EntryStatus.STOPPED,
        source=EntrySource.MANUAL,
        started_at=started_at,
        ended_at=ended_at,
        **data,
    )
    entry.duration_seconds = _duration(entry)
    entry.save()
    audit(user=user, entity_type="time_entry", entity_id=entry.id, action="CREATE")
    return entry, _overlap_warnings(user, entry)


def _values(entry: TimeEntry) -> dict[str, Any]:
    return {
        "started_at": entry.started_at.isoformat(),
        "ended_at": entry.ended_at.isoformat() if entry.ended_at else None,
        "duration_seconds": entry.duration_seconds,
        "task_id": str(entry.task_id) if entry.task_id else None,
        "category_id": str(entry.category_id) if entry.category_id else None,
        "description": entry.description,
        "is_focus": entry.is_focus,
    }


@transaction.atomic
def entry_update(
    *, user: User, entry: TimeEntry, data: dict[str, Any], reason: str = ""
) -> tuple[TimeEntry, list[dict[str, Any]]]:
    if entry.status != EntryStatus.STOPPED:
        raise ConflictError("Stop the timer before editing it.", code="TIMER_ALREADY_RUNNING")
    before = _values(entry)
    links = {k: v for k, v in data.items() if k in LINK_FIELDS}
    _check_links(user, links)
    start = data.get("started_at", entry.started_at)
    end = data.get("ended_at", entry.ended_at)
    if (start, end) != (entry.started_at, entry.ended_at):
        _validate_manual(user, start, end, links.get("task", entry.task), exclude=entry.id)
        entry.started_at, entry.ended_at = start, end
        span = int((end - start).total_seconds())
        entry.paused_seconds = min(entry.paused_seconds, span)
    for k, v in links.items():
        setattr(entry, k, v)
    entry.duration_seconds = _duration(entry)
    entry.save()
    after = _values(entry)
    if after != before:
        TimeEntryRevision.objects.create(
            user=user, time_entry=entry, old_values=before, new_values=after, reason=reason.strip()
        )
    return entry, _overlap_warnings(user, entry)


def entry_delete(*, user: User, entry: TimeEntry) -> None:
    if entry.status != EntryStatus.STOPPED:
        raise ConflictError("Use discard for the running timer.", code="TIMER_ALREADY_RUNNING")
    entry.deleted_at = now()
    entry.save(update_fields=["deleted_at", "updated_at"])
    audit(user=user, entity_type="time_entry", entity_id=entry.id, action="DELETE")
