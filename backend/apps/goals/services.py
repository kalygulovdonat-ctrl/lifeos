"""Write side of goals (SDD §4.7, §5.7, BR-040…BR-045)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction

from apps.accounts.models import Category, User
from apps.goals import progress
from apps.goals.models import (
    Goal,
    GoalProgress,
    GoalStatus,
    GoalStatusChange,
    GoalTask,
    Milestone,
    MilestoneStatus,
    ProgressSource,
    ProgressType,
)
from apps.tasks.models import Task
from common.audit import audit, diff
from common.exceptions import ConflictError, DomainValidationError
from common.time import local_today, now

MAX_DEPTH = 6
FIELDS = {
    "parent",
    "level",
    "title",
    "description",
    "category",
    "start_date",
    "target_date",
    "progress_type",
    "metric_unit",
    "start_value",
    "target_value",
    "current_value",
}
# Status actions of POST /goals/{id}/status/
ACTIONS: dict[str, tuple[set[str], str]] = {
    "PAUSE": ({GoalStatus.ACTIVE}, GoalStatus.PAUSED),
    "RESUME": ({GoalStatus.PAUSED}, GoalStatus.ACTIVE),
    "COMPLETE": ({GoalStatus.ACTIVE, GoalStatus.PAUSED}, GoalStatus.COMPLETED),
    "ABANDON": ({GoalStatus.ACTIVE, GoalStatus.PAUSED}, GoalStatus.ABANDONED),
    "REOPEN": ({GoalStatus.COMPLETED, GoalStatus.ABANDONED}, GoalStatus.ACTIVE),
}


def _invalid(field: str, message: str) -> DomainValidationError:
    return DomainValidationError(details={field: [message]})


def _check_parent(user: User, goal: Goal | None, parent: Goal | None) -> None:
    if parent is None:
        return
    if parent.user_id != user.id:
        raise _invalid("parent_id", "Unknown goal.")
    depth, node = 1, parent
    while node is not None:
        if goal is not None and node.id == goal.id:
            raise _invalid("parent_id", "A goal cannot be inside itself.")
        depth += 1
        if depth > MAX_DEPTH:
            raise _invalid("parent_id", f"Goals can be nested at most {MAX_DEPTH} levels deep.")
        node = Goal.objects.filter(id=node.parent_id).first() if node.parent_id else None
    if goal is not None:  # the goal's own subtree also counts towards the depth limit

        def height(g: Goal) -> int:
            return 1 + max((height(c) for c in Goal.objects.filter(parent=g)), default=0)

        if depth - 1 + height(goal) > MAX_DEPTH:
            raise _invalid("parent_id", f"Goals can be nested at most {MAX_DEPTH} levels deep.")


def _validate(user: User, goal: Goal | None, d: dict[str, Any]) -> None:
    if not str(d.get("title", "")).strip():
        raise _invalid("title", "Title must not be blank.")
    category: Category | None = d.get("category")
    if category is not None and category.user_id != user.id:
        raise _invalid("category_id", "Unknown category.")
    if d.get("target_date") and d.get("start_date") and d["target_date"] < d["start_date"]:
        raise _invalid("target_date", "Must not be before start_date (BR-041).")
    if d.get("progress_type") == ProgressType.METRIC:
        if d.get("start_value") is None or d.get("target_value") is None:
            raise _invalid("target_value", "A metric goal needs start and target values.")
        if d["start_value"] == d["target_value"]:
            raise _invalid("target_value", "Target must differ from the start value.")
    _check_parent(user, goal, d.get("parent"))


def recalculate(
    goal: Goal, *, source: str = ProgressSource.RECALC, source_id: Any = None, note: str = ""
) -> Goal:
    """Synchronous recompute; history row only when the percentage changes (SDD §5.7)."""
    pt = goal.progress_type
    if pt == ProgressType.METRIC:
        pct = progress.metric(goal.start_value, goal.target_value, goal.current_value)
    elif pt == ProgressType.MILESTONES:
        pct = progress.milestones(goal.milestones.all())
    elif pt == ProgressType.TASKS:
        pct = progress.tasks(GoalTask.objects.filter(goal=goal).select_related("task"))
    else:
        pct = progress.manual(goal.current_value)
    if pct != goal.progress_pct:
        reached = pct >= 100 > goal.progress_pct and goal.status == GoalStatus.ACTIVE
        goal.progress_pct = pct
        goal.save(update_fields=["progress_pct", "updated_at"])
        GoalProgress.objects.create(
            user_id=goal.user_id,
            goal=goal,
            value=goal.current_value if pt in (ProgressType.METRIC, ProgressType.MANUAL) else None,
            progress_pct=pct,
            source=source,
            source_id=source_id,
            note=note,
        )
        if reached:
            from apps.notifications.services import notification_create

            notification_create(
                user=goal.user,
                type="GOAL_COMPLETED",
                message_key="goalReached",
                params={"title": goal.title},
                link=f"/goals/{goal.id}",
            )
    return goal


@transaction.atomic
def goal_create(*, user: User, data: dict[str, Any]) -> Goal:
    d = {k: v for k, v in data.items() if k in FIELDS}
    d.setdefault("start_date", local_today(user.profile.timezone))
    _validate(user, None, d)
    d["title"] = d["title"].strip()
    if d.get("progress_type") == ProgressType.METRIC and d.get("current_value") is None:
        d["current_value"] = d["start_value"]
    goal = Goal.objects.create(user=user, **d)
    GoalStatusChange.objects.create(user=user, goal=goal, from_status=None, to_status=goal.status)
    recalculate(goal)
    audit(user=user, entity_type="goal", entity_id=goal.id, action="CREATE")
    return goal


@transaction.atomic
def goal_update(*, user: User, goal: Goal, data: dict[str, Any]) -> Goal:
    d = {k: v for k, v in data.items() if k in FIELDS}
    merged = {f: getattr(goal, f) for f in FIELDS} | d
    _validate(user, goal, merged)
    changes = diff(goal, d)
    for k, v in d.items():
        setattr(goal, k, v.strip() if k == "title" else v)
    goal.save()
    recalculate(goal)
    if changes:
        audit(user=user, entity_type="goal", entity_id=goal.id, action="UPDATE", changes=changes)
    return goal


@transaction.atomic
def goal_change_status(*, user: User, goal: Goal, action: str, reason: str = "") -> Goal:
    allowed, target = ACTIONS[action]
    if goal.status not in allowed:
        raise ConflictError(
            f"Cannot {action.lower()} a goal that is {goal.status}.",
            code="INVALID_STATUS_TRANSITION",
            details={"from": goal.status, "action": action},
        )
    old = goal.status
    goal.status = target
    goal.completed_at = now() if target == GoalStatus.COMPLETED else None
    goal.save(update_fields=["status", "completed_at", "updated_at"])
    GoalStatusChange.objects.create(
        user=user, goal=goal, from_status=old, to_status=target, reason=reason.strip()
    )
    audit(
        user=user, entity_type="goal", entity_id=goal.id, action="STATUS", changes={"status": [old, target]}
    )
    return goal


@transaction.atomic
def goal_set_progress(*, user: User, goal: Goal, value: Decimal, note: str = "") -> Goal:
    if goal.progress_type not in (ProgressType.METRIC, ProgressType.MANUAL):
        raise ConflictError(
            "Progress of this goal is calculated automatically.", code="GOAL_PROGRESS_AUTOMATIC"
        )
    if goal.progress_type == ProgressType.MANUAL and not Decimal(0) <= value <= Decimal(100):
        raise _invalid("value", "Manual progress is a percentage 0..100.")
    goal.current_value = value
    goal.save(update_fields=["current_value", "updated_at"])
    before = goal.progress_pct
    recalculate(goal, source=ProgressSource.MANUAL, note=note.strip())
    if goal.progress_pct == before:  # value changed but not the percentage: still worth a history row
        GoalProgress.objects.create(
            user=user,
            goal=goal,
            value=value,
            progress_pct=goal.progress_pct,
            source=ProgressSource.MANUAL,
            note=note.strip(),
        )
    return goal


def goal_delete(*, user: User, goal: Goal) -> None:
    goal.deleted_at = now()
    goal.save(update_fields=["deleted_at", "updated_at"])
    Goal.objects.filter(parent=goal).update(parent=None)
    audit(user=user, entity_type="goal", entity_id=goal.id, action="DELETE")


# ---------------------------------------------------------------- tasks & milestones


@transaction.atomic
def goal_link_task(*, user: User, goal: Goal, task: Task, weight: Decimal = Decimal(1)) -> GoalTask:
    if task.user_id != user.id:
        raise _invalid("task_id", "Unknown task.")
    try:
        with transaction.atomic():
            link = GoalTask.objects.create(user=user, goal=goal, task=task, weight=weight)
    except IntegrityError:
        link = GoalTask.objects.get(goal=goal, task=task)
    recalculate(goal, source=ProgressSource.TASK, source_id=task.id)
    return link


@transaction.atomic
def goal_unlink_task(*, user: User, goal: Goal, task: Task) -> None:
    GoalTask.objects.filter(user=user, goal=goal, task=task).delete()
    recalculate(goal, source=ProgressSource.TASK, source_id=task.id)


def recalc_for_task(task: Task) -> None:
    """Called by the tasks module after a status change or deletion (domain hook)."""
    for goal in Goal.objects.filter(task_links__task=task).distinct():
        recalculate(goal, source=ProgressSource.TASK, source_id=task.id)


def milestone_create(*, user: User, goal: Goal, data: dict[str, Any]) -> Milestone:
    if not str(data.get("title", "")).strip():
        raise _invalid("title", "Title must not be blank.")
    last = goal.milestones.order_by("-sort_order").first()
    m = Milestone.objects.create(
        user=user,
        goal=goal,
        title=data["title"].strip(),
        due_date=data.get("due_date"),
        weight=data.get("weight") or Decimal(1),
        sort_order=(last.sort_order + 1) if last else 0,
    )
    recalculate(goal, source=ProgressSource.MILESTONE, source_id=m.id)
    return m


@transaction.atomic
def milestone_update(*, user: User, milestone: Milestone, data: dict[str, Any]) -> Milestone:
    if "title" in data:
        if not data["title"].strip():
            raise _invalid("title", "Title must not be blank.")
        milestone.title = data["title"].strip()
    for k in ("due_date", "weight", "sort_order"):
        if k in data:
            setattr(milestone, k, data[k])
    if "status" in data and data["status"] != milestone.status:
        milestone.status = data["status"]
        milestone.completed_at = now() if milestone.status == MilestoneStatus.COMPLETED else None
    milestone.save()
    recalculate(milestone.goal, source=ProgressSource.MILESTONE, source_id=milestone.id)
    return milestone


def milestone_complete(*, user: User, milestone: Milestone) -> Milestone:
    return milestone_update(user=user, milestone=milestone, data={"status": MilestoneStatus.COMPLETED})


@transaction.atomic
def milestone_delete(*, user: User, milestone: Milestone) -> None:
    goal = milestone.goal
    milestone.delete()
    recalculate(goal, source=ProgressSource.MILESTONE)
