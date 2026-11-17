"""Read side of goals. Every function takes the owner first (BR-002)."""

from __future__ import annotations

from uuid import UUID

from django.db.models import Count, Prefetch, Q, QuerySet

from apps.accounts.models import User
from apps.goals.models import Goal, GoalProgress, GoalStatusChange, GoalTask, Milestone
from common.exceptions import NotFoundError


def _annotated(qs: QuerySet[Goal]) -> QuerySet[Goal]:
    return qs.select_related("category").annotate(
        milestones_total=Count("milestones", distinct=True),
        milestones_done=Count("milestones", filter=Q(milestones__status="COMPLETED"), distinct=True),
        tasks_total=Count("task_links", filter=Q(task_links__task__deleted_at__isnull=True), distinct=True),
        tasks_done=Count(
            "task_links",
            filter=Q(task_links__task__status="COMPLETED", task_links__task__deleted_at__isnull=True),
            distinct=True,
        ),
    )


def goal_list(
    user: User, *, statuses: list[str] | None = None, level: str | None = None, archived: bool = False
) -> QuerySet[Goal]:
    qs = Goal.objects.filter(user=user, is_archived=archived)
    if statuses:
        qs = qs.filter(status__in=statuses)
    if level:
        qs = qs.filter(level=level)
    return _annotated(qs)


def goal_get(user: User, goal_id: UUID | str) -> Goal:
    try:
        return (
            _annotated(Goal.objects.filter(user=user))
            .prefetch_related(
                Prefetch(
                    "milestones", queryset=Milestone.objects.order_by("sort_order", "due_date", "created_at")
                )
            )
            .get(id=goal_id)
        )
    except (Goal.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def linked_tasks(user: User, goal: Goal) -> QuerySet[GoalTask]:
    return GoalTask.objects.filter(user=user, goal=goal, task__deleted_at__isnull=True).select_related("task")


def progress_history(user: User, goal: Goal) -> QuerySet[GoalProgress]:
    return GoalProgress.objects.filter(user=user, goal=goal)


def status_history(user: User, goal: Goal) -> QuerySet[GoalStatusChange]:
    return GoalStatusChange.objects.filter(user=user, goal=goal)


def milestone_get(user: User, milestone_id: UUID | str) -> Milestone:
    try:
        return Milestone.objects.select_related("goal").get(
            user=user, id=milestone_id, goal__deleted_at__isnull=True
        )
    except (Milestone.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def build_tree(goals: list[Goal]) -> list[tuple[Goal, list]]:
    """Nested (goal, children) pairs; goals whose parent is outside the list become roots."""
    ids = {g.id for g in goals}
    children: dict[UUID | None, list[Goal]] = {}
    for g in goals:
        key = g.parent_id if g.parent_id in ids else None
        children.setdefault(key, []).append(g)

    def node(g: Goal) -> tuple[Goal, list]:
        return g, [node(c) for c in children.get(g.id, [])]

    return [node(g) for g in children.get(None, [])]
