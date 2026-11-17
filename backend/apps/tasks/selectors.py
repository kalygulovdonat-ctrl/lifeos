"""Read side of tasks (SDD §6.2). Every function takes the owner first (BR-002)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from django.db.models import Case, Count, IntegerField, OuterRef, Q, QuerySet, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.accounts.models import User
from apps.tasks.models import OPEN_STATUSES, Subtask, Task, TaskStatus, TaskStatusChange
from common.exceptions import NotFoundError
from common.time import now, period_bounds

ORDERINGS = {
    "due_at": "due_at",
    "-due_at": "-due_at",
    "priority": "priority_rank",
    "-priority": "-priority_rank",
    "created_at": "created_at",
    "-created_at": "-created_at",
    "title": "title",
    "sort_order": "sort_order",
}


def _annotated(qs: QuerySet[Task]) -> QuerySet[Task]:
    from apps.time_tracking.models import TimeEntry  # actual time is derived, never stored (SDD §4.5)

    actual = (
        TimeEntry.objects.filter(task=OuterRef("pk"), status="STOPPED")
        .order_by()
        .values("task")
        .annotate(total=Sum("duration_seconds"))
        .values("total")
    )
    return (
        qs.select_related("category")
        .prefetch_related("tags", "goal_links__goal")
        .annotate(
            subtasks_total=Count("subtasks", distinct=True),
            subtasks_done=Count("subtasks", filter=Q(subtasks__is_done=True), distinct=True),
            actual_seconds=Coalesce(Subquery(actual, output_field=IntegerField()), Value(0)),
            priority_rank=Case(
                When(priority="LOW", then=Value(0)),
                When(priority="MEDIUM", then=Value(1)),
                When(priority="HIGH", then=Value(2)),
                When(priority="URGENT", then=Value(3)),
                output_field=IntegerField(),
            ),
        )
    )


def task_get(user: User, task_id: UUID | str) -> Task:
    try:
        return _annotated(Task.objects.filter(user=user)).get(id=task_id)
    except (Task.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


@dataclass
class TaskFilters:
    statuses: list[str] = field(default_factory=list)
    priorities: list[str] = field(default_factory=list)
    category_id: UUID | None = None
    tag_id: UUID | None = None
    q: str = ""
    due_from: date | None = None
    due_to: date | None = None
    inbox: bool | None = None
    overdue: bool = False
    archived: bool = False
    ordering: str = ""


def task_list(user: User, filters: TaskFilters | None = None) -> QuerySet[Task]:
    f = filters or TaskFilters()
    qs = Task.objects.filter(user=user, is_archived=f.archived)
    tz = user.profile.timezone
    if f.statuses:
        qs = qs.filter(status__in=f.statuses)
    if f.priorities:
        qs = qs.filter(priority__in=f.priorities)
    if f.category_id:
        qs = qs.filter(category_id=f.category_id)
    if f.tag_id:
        qs = qs.filter(tags__id=f.tag_id)
    if f.q:
        qs = qs.filter(Q(title__icontains=f.q) | Q(description__icontains=f.q))
    if f.due_from:
        qs = qs.filter(due_at__gte=period_bounds(tz, "day", f.due_from).start)
    if f.due_to:
        qs = qs.filter(due_at__lt=period_bounds(tz, "day", f.due_to).end)
    if f.inbox is True:
        qs = qs.filter(triaged_at__isnull=True)
    elif f.inbox is False:
        qs = qs.filter(triaged_at__isnull=False)
    if f.overdue:
        qs = qs.filter(status__in=OPEN_STATUSES, due_at__lt=now())
    qs = _annotated(qs).distinct()
    order = ORDERINGS.get(f.ordering)
    if order:
        return qs.order_by(order, "-created_at")
    return qs.order_by("sort_order", "-created_at")


def inbox(user: User) -> QuerySet[Task]:
    return task_list(user, TaskFilters(inbox=True, statuses=list(OPEN_STATUSES)))


def inbox_count(user: User) -> int:
    return Task.objects.filter(
        user=user, triaged_at__isnull=True, is_archived=False, status__in=OPEN_STATUSES
    ).count()


@dataclass
class DayTasks:
    due: list[Task]
    overdue: list[Task]
    completed: list[Task]


def tasks_for_day(user: User, day: date) -> DayTasks:
    """Open tasks due or scheduled that day, overdue ones, and those completed that day."""
    profile = user.profile
    bounds = period_bounds(profile.timezone, "day", day)
    base = _annotated(Task.objects.filter(user=user, is_archived=False))
    open_qs = base.filter(status__in=OPEN_STATUSES)
    due = list(
        open_qs.filter(
            Q(due_at__gte=bounds.start, due_at__lt=bounds.end)
            | Q(scheduled_start__lt=bounds.end, scheduled_end__gt=bounds.start)
        ).order_by("-priority_rank", "due_at")
    )
    cutoff = min(bounds.start, now())
    overdue = list(open_qs.filter(due_at__lt=cutoff).order_by("due_at"))
    completed = list(
        base.filter(status=TaskStatus.COMPLETED, completed_at__gte=bounds.start, completed_at__lt=bounds.end)
    )
    return DayTasks(due=due, overdue=overdue, completed=completed)


def task_history(user: User, task: Task) -> QuerySet[TaskStatusChange]:
    return TaskStatusChange.objects.filter(user=user, task=task)


def subtask_list(user: User, task: Task) -> QuerySet[Subtask]:
    return Subtask.objects.filter(user=user, task=task)


def subtask_get(user: User, subtask_id: UUID | str) -> Subtask:
    try:
        return Subtask.objects.select_related("task").get(
            user=user, id=subtask_id, task__deleted_at__isnull=True
        )
    except (Subtask.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def owned_task_or_none(user: User, task_id: UUID | str | None) -> Task | None:
    """Resolves a task id from input; a foreign or unknown id is a validation error upstream."""
    if task_id is None:
        return None
    return Task.objects.filter(user=user, id=task_id).first()


def is_overdue(task: Task, at: datetime | None = None) -> bool:
    return task.status in OPEN_STATUSES and task.due_at is not None and task.due_at < (at or now())
