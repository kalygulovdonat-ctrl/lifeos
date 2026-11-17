"""Write side of tasks (SDD §4.5, §6.2). Business rules live here, not in views."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Max

from apps.accounts.models import Category, Tag, User
from apps.tasks.models import Subtask, Task, TaskStatus, TaskStatusChange
from common.audit import audit, diff
from common.exceptions import ConflictError, DomainValidationError
from common.models import ActorType
from common.time import now

MAX_SUBTASKS = 100
S = TaskStatus

# TASK-004 / SDD §4.5 transition matrix.
TRANSITIONS: dict[str, set[str]] = {
    S.BACKLOG: {S.TODO, S.IN_PROGRESS, S.COMPLETED, S.CANCELLED},
    S.TODO: {S.BACKLOG, S.IN_PROGRESS, S.POSTPONED, S.COMPLETED, S.CANCELLED},
    S.IN_PROGRESS: {S.BACKLOG, S.TODO, S.POSTPONED, S.COMPLETED, S.CANCELLED},
    S.POSTPONED: {S.BACKLOG, S.TODO, S.IN_PROGRESS, S.POSTPONED, S.COMPLETED, S.CANCELLED},
    S.COMPLETED: {S.TODO},
    S.CANCELLED: {S.BACKLOG, S.TODO},
}
CREATE_STATUSES = {S.BACKLOG, S.TODO, S.IN_PROGRESS}

EDITABLE = {
    "title",
    "description",
    "priority",
    "category",
    "due_at",
    "due_has_time",
    "scheduled_start",
    "scheduled_end",
    "estimated_minutes",
    "sort_order",
}
# Setting any of these during triage takes the task out of the Inbox (SDD §1, TASK-013).
TRIAGE_FIELDS = {"due_at", "category", "priority", "scheduled_start"}


def end_of_local_day(day: date, tz_name: str) -> datetime:
    """A date-only deadline means "by the end of that day" in the user's time zone."""
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=ZoneInfo(tz_name)) - timedelta(
        microseconds=1
    )


def _resolve_due(user: User, data: dict[str, Any]) -> None:
    """`due_date` (YYYY-MM-DD) → end of that local day; `due_at` → exact moment."""
    if "due_date" in data:
        day = data.pop("due_date")
        if day is None:
            data["due_at"], data["due_has_time"] = None, False
        else:
            data["due_at"] = end_of_local_day(day, user.profile.timezone)
            data["due_has_time"] = False
    elif "due_at" in data:
        data["due_has_time"] = data["due_at"] is not None


def _check_category(user: User, category: Category | None) -> None:
    if category is not None and category.user_id != user.id:
        raise DomainValidationError(details={"category_id": ["Unknown category."]})


def _check_window(start: datetime | None, end: datetime | None) -> None:
    if start and end and end <= start:
        raise DomainValidationError(details={"scheduled_end": ["Must be later than scheduled_start."]})


def _set_tags(user: User, task: Task, tags: list[Tag]) -> None:
    if any(t.user_id != user.id for t in tags):
        raise DomainValidationError(details={"tag_ids": ["Unknown tag."]})
    task.tags.set(tags)


def _log(
    task: Task,
    from_status: str | None,
    to_status: str,
    *,
    reason: str = "",
    old_due: datetime | None = None,
    new_due: datetime | None = None,
    actor: str = ActorType.USER,
) -> None:
    TaskStatusChange.objects.create(
        user_id=task.user_id,
        task=task,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        old_due_at=old_due,
        new_due_at=new_due,
        actor_type=actor,
    )


@transaction.atomic
def task_create(
    *,
    user: User,
    title: str,
    status: str = S.TODO,
    tags: list[Tag] | None = None,
    subtasks: list[str] | None = None,
    inbox: bool = False,
    **data: Any,
) -> Task:
    if status not in CREATE_STATUSES:
        raise DomainValidationError(
            details={"status": ["A new task starts as BACKLOG, TODO or IN_PROGRESS."]}
        )
    if not title.strip():
        raise DomainValidationError(details={"title": ["Title must not be blank."]})
    _resolve_due(user, data)
    data = {k: v for k, v in data.items() if k in EDITABLE}
    _check_category(user, data.get("category"))
    _check_window(data.get("scheduled_start"), data.get("scheduled_end"))
    subtasks = subtasks or []
    if len(subtasks) > MAX_SUBTASKS:
        raise DomainValidationError(details={"subtasks": [f"At most {MAX_SUBTASKS} subtasks."]})

    task = Task.objects.create(
        user=user,
        title=title.strip(),
        status=status,
        triaged_at=None if inbox else now(),
        **data,
    )
    if tags:
        _set_tags(user, task, tags)
    Subtask.objects.bulk_create(
        Subtask(user=user, task=task, title=t.strip(), sort_order=i)
        for i, t in enumerate(subtasks)
        if t.strip()
    )
    _log(task, None, status, new_due=task.due_at)
    audit(user=user, entity_type="task", entity_id=task.id, action="CREATE")
    return task


def task_quick_create(*, user: User, title: str) -> Task:
    """Quick capture: title only, lands in the Inbox (TASK-013)."""
    return task_create(user=user, title=title, inbox=True)


@transaction.atomic
def task_update(*, user: User, task: Task, data: dict[str, Any]) -> Task:
    data = dict(data)
    tags = data.pop("tags", None)
    _resolve_due(user, data)
    data = {k: v for k, v in data.items() if k in EDITABLE}
    if "title" in data:
        if not data["title"].strip():
            raise DomainValidationError(details={"title": ["Title must not be blank."]})
        data["title"] = data["title"].strip()
    _check_category(user, data.get("category"))
    _check_window(
        data.get("scheduled_start", task.scheduled_start), data.get("scheduled_end", task.scheduled_end)
    )
    changes = diff(task, data)
    for k, v in data.items():
        setattr(task, k, v)
    if task.triaged_at is None and TRIAGE_FIELDS & {k for k, v in data.items() if v is not None}:
        task.triaged_at = now()
    task.save()
    if tags is not None:
        _set_tags(user, task, tags)
    if changes:
        audit(user=user, entity_type="task", entity_id=task.id, action="UPDATE", changes=changes)
    return task


@transaction.atomic
def task_change_status(
    *,
    user: User,
    task: Task,
    status: str,
    reason: str = "",
    new_due_at: datetime | None = None,
    actor: str = ActorType.USER,
) -> Task:
    task = Task.objects.select_for_update().get(pk=task.pk, user=user)
    current = task.status
    if status not in TRANSITIONS.get(current, set()):
        raise ConflictError(
            f"Cannot change status from {current} to {status}.",
            code="INVALID_STATUS_TRANSITION",
            details={"from": current, "to": status},
        )
    reason = (reason or "").strip()
    old_due = task.due_at
    if status == S.POSTPONED:
        if new_due_at is None and not reason:
            raise DomainValidationError(details={"reason": ["Give a new due date or a reason (BR-022)."]})
        task.postponed_count += 1
        if new_due_at is not None:
            task.due_at = new_due_at
    moment = now()
    task.completed_at = moment if status == S.COMPLETED else None
    task.cancelled_at = moment if status == S.CANCELLED else None
    if status in (S.COMPLETED, S.CANCELLED) and task.triaged_at is None:
        task.triaged_at = moment
    task.status = status
    task.save()
    _log(task, current, status, reason=reason, old_due=old_due, new_due=task.due_at, actor=actor)
    audit(
        user=user,
        entity_type="task",
        entity_id=task.id,
        action="STATUS",
        changes={"status": [current, status]},
        actor_type=actor,
    )
    return task


def task_complete(*, user: User, task: Task) -> Task:
    return task_change_status(user=user, task=task, status=S.COMPLETED)


def task_postpone(*, user: User, task: Task, new_due_at: datetime | None = None, reason: str = "") -> Task:
    return task_change_status(user=user, task=task, status=S.POSTPONED, reason=reason, new_due_at=new_due_at)


def task_triage(*, user: User, task: Task) -> Task:
    if task.triaged_at is None:
        task.triaged_at = now()
        task.save(update_fields=["triaged_at", "updated_at"])
    return task


def task_set_archived(*, user: User, task: Task, archived: bool) -> Task:
    task.is_archived = archived
    task.save(update_fields=["is_archived", "updated_at"])
    audit(user=user, entity_type="task", entity_id=task.id, action="ARCHIVE" if archived else "RESTORE")
    return task


def task_delete(*, user: User, task: Task) -> None:
    """Soft delete; status history is kept (BR-026)."""
    task.deleted_at = now()
    task.save(update_fields=["deleted_at", "updated_at"])
    audit(user=user, entity_type="task", entity_id=task.id, action="DELETE")


# ---------------------------------------------------------------- subtasks


def subtask_create(*, user: User, task: Task, title: str) -> Subtask:
    if not title.strip():
        raise DomainValidationError(details={"title": ["Title must not be blank."]})
    if Subtask.objects.filter(task=task).count() >= MAX_SUBTASKS:
        raise DomainValidationError(details={"subtasks": [f"At most {MAX_SUBTASKS} subtasks."]})
    last = Subtask.objects.filter(task=task).aggregate(m=Max("sort_order"))["m"]
    return Subtask.objects.create(
        user=user, task=task, title=title.strip(), sort_order=0 if last is None else last + 1
    )


def subtask_update(*, user: User, subtask: Subtask, data: dict[str, Any]) -> Subtask:
    if "title" in data:
        if not data["title"].strip():
            raise DomainValidationError(details={"title": ["Title must not be blank."]})
        subtask.title = data["title"].strip()
    if "is_done" in data and data["is_done"] != subtask.is_done:
        subtask.is_done = data["is_done"]
        subtask.done_at = now() if subtask.is_done else None
    if "sort_order" in data:
        subtask.sort_order = data["sort_order"]
    subtask.save()
    return subtask


def subtask_delete(*, user: User, subtask: Subtask) -> None:
    subtask.delete()


@transaction.atomic
def subtask_reorder(*, user: User, task: Task, ids: list[UUID]) -> list[Subtask]:
    items = {s.id: s for s in Subtask.objects.filter(user=user, task=task)}
    if set(ids) != set(items):
        raise DomainValidationError(details={"ids": ["Provide every subtask id of this task exactly once."]})
    for order, sid in enumerate(ids):
        items[sid].sort_order = order
    Subtask.objects.bulk_update(items.values(), ["sort_order"])
    return sorted(items.values(), key=lambda s: s.sort_order)
