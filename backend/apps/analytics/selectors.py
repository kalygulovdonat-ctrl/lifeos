"""Analytics (SDD §5): objective metrics with explicit numerators and denominators.

Metrics are computed live from facts. A period is "final" once it has ended in the user's
time zone; weekly reviews freeze their own copy (stats_snapshot), so history never shifts
under a completed review (BR-066).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from django.db.models import Q

from apps.accounts.models import Category, User
from apps.goals.models import Goal, GoalStatus
from apps.habits import logic as habit_logic
from apps.habits.models import Habit, HabitLog
from apps.tasks.models import Task, TaskStatus, TaskStatusChange
from apps.time_tracking import selectors as time_selectors
from apps.time_tracking.models import EntryStatus, TimeEntry
from common.time import local_today, now, period_bounds

FORMULA_VERSION = "2026.1"
Period = Literal["day", "week", "month"]


def metric(
    key: str, numerator: float | None, denominator: float | None, *, value: Any = None
) -> dict[str, Any]:
    """Standard metric shape (SDD §7.2). Empty denominator → value null, reason NO_DATA (§5.10)."""
    if value is None and denominator:
        value = round(numerator / denominator, 4) if numerator is not None else None
    result = {"key": key, "value": value, "numerator": numerator, "denominator": denominator}
    if value is None:
        result["reason"] = "NO_DATA"
    return result


@dataclass(frozen=True)
class Window:
    period: Period
    first: date
    last: date
    start: datetime
    end: datetime
    is_final: bool


def window(user: User, period: Period, anchor: date) -> Window:
    profile = user.profile
    b = period_bounds(profile.timezone, period, anchor, profile.week_start)
    today = local_today(profile.timezone)
    return Window(period, b.first_day, b.last_day, b.start, b.end, b.last_day < today)


def previous(user: User, w: Window) -> Window:
    return window(user, w.period, w.first - timedelta(days=1))


# ---------------------------------------------------------------- §5.1 tasks


def task_metrics(user: User, w: Window) -> dict[str, Any]:
    moment = now()
    tasks = Task.objects.filter(user=user)
    completed = tasks.filter(status=TaskStatus.COMPLETED, completed_at__gte=w.start, completed_at__lt=w.end)
    overdue_open = tasks.filter(
        due_at__gte=w.start, due_at__lt=min(w.end, moment), is_archived=False
    ).exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.BACKLOG])
    done, late = completed.count(), overdue_open.count()
    postponed = TaskStatusChange.objects.filter(
        user=user, to_status=TaskStatus.POSTPONED, changed_at__gte=w.start, changed_at__lt=w.end
    ).count()
    created = tasks.filter(created_at__gte=w.start, created_at__lt=w.end).count()
    return {
        "completion_rate": metric("task_completion_rate", done, done + late),
        "completed": done,
        "overdue_open": late,
        "postponed": postponed,
        "created": created,
    }


# ---------------------------------------------------------------- §5.3 habits


def habit_metrics(user: User, w: Window) -> dict[str, Any]:
    today = local_today(user.profile.timezone)
    items = []
    success = eligible = 0
    habits = Habit.objects.filter(user=user, is_archived=False).prefetch_related("schedules", "pauses")
    for habit in habits:
        logs = list(HabitLog.objects.filter(habit=habit, is_voided=False))
        stats = habit_logic.compute_stats(
            habit,
            list(habit.schedules.all()),
            list(habit.pauses.all()),
            logs,
            w.first,
            min(w.last, today),
            today,
            user.profile.week_start,
        )
        success += stats.success
        eligible += stats.eligible
        items.append(
            {
                "id": str(habit.id),
                "name": habit.name,
                "color": habit.color,
                "consistency": stats.consistency,
                "success": stats.success,
                "eligible": stats.eligible,
                "current_streak": stats.current_streak,
            }
        )
    items.sort(key=lambda i: (i["consistency"] is None, -(i["consistency"] or 0)))
    return {"consistency": metric("habit_consistency", success, eligible), "habits": items}


# ---------------------------------------------------------------- §5.2, §5.5, §5.6 time


def time_metrics(user: User, w: Window) -> dict[str, Any]:
    focus = time_selectors.tracked_seconds(user, w.start, w.end, focus_only=True)
    tracked = time_selectors.tracked_seconds(user, w.start, w.end)
    pva = time_selectors.plan_vs_actual(user, w.start, w.end)
    return {
        "focus_hours": metric("focus_hours", None, None, value=round(focus / 3600, 2)),
        "tracked_hours": round(tracked / 3600, 2),
        "schedule_accuracy": metric("schedule_accuracy", pva.matched_minutes, pva.planned_minutes),
        "planned_minutes": pva.planned_minutes,
        "actual_minutes": pva.actual_minutes,
        "unplanned_minutes": pva.unplanned_minutes,
        "distribution": time_distribution(user, w),
    }


def time_distribution(user: User, w: Window) -> list[dict[str, Any]]:
    """Seconds per category, overlapping sessions merged inside each category (SDD §5.6)."""
    per_category: dict[str | None, list[tuple[datetime, datetime]]] = defaultdict(list)
    entries = TimeEntry.objects.filter(
        user=user, status=EntryStatus.STOPPED, started_at__lt=w.end, ended_at__gt=w.start
    )
    for e in entries:
        s, f = max(e.started_at, w.start), min(e.ended_at, w.end)
        if f > s:
            per_category[str(e.category_id) if e.category_id else None].append((s, f))
    totals = {k: time_selectors.merged_seconds(v) for k, v in per_category.items()}
    grand = sum(totals.values())
    names = {str(c.id): c for c in Category.objects.filter(user=user, id__in=[k for k in totals if k])}
    rows = []
    for key, seconds in sorted(totals.items(), key=lambda kv: -kv[1]):
        cat = names.get(key) if key else None
        rows.append(
            {
                "category_id": key,
                "name": cat.name if cat else None,
                "system_key": cat.system_key if cat and not cat.is_name_custom else None,
                "color": cat.color if cat else None,
                "minutes": seconds // 60,
                "share": round(seconds / grand, 4) if grand else None,
            }
        )
    return rows


# ---------------------------------------------------------------- §5.7 goals


def goal_metrics(user: User, w: Window) -> dict[str, Any]:
    goals = Goal.objects.filter(user=user, is_archived=False)
    active = goals.filter(status=GoalStatus.ACTIVE).order_by("-progress_pct")
    completed = goals.filter(completed_at__gte=w.start, completed_at__lt=w.end).count()
    return {
        "active": [
            {
                "id": str(g.id),
                "title": g.title,
                "progress_pct": float(g.progress_pct),
                "target_date": g.target_date,
            }
            for g in active[:8]
        ],
        "completed_in_period": completed,
    }


# ---------------------------------------------------------------- per-day series


def daily_series(user: User, w: Window) -> list[dict[str, Any]]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(user.profile.timezone)
    days = [w.first + timedelta(days=i) for i in range((w.last - w.first).days + 1)]
    done_by_day: dict[date, int] = defaultdict(int)
    for completed_at in Task.objects.filter(
        user=user, status=TaskStatus.COMPLETED, completed_at__gte=w.start, completed_at__lt=w.end
    ).values_list("completed_at", flat=True):
        done_by_day[completed_at.astimezone(tz).date()] += 1
    habit_done: dict[date, int] = defaultdict(int)
    for log_date in (
        HabitLog.objects.filter(
            user=user, is_voided=False, status="DONE", log_date__gte=w.first, log_date__lte=w.last
        )
        .values_list("log_date", flat=True)
        .distinct()
    ):
        habit_done[log_date] += 1
    series = []
    for d in days:
        b = period_bounds(user.profile.timezone, "day", d)
        series.append(
            {
                "date": d.isoformat(),
                "tasks_completed": done_by_day[d],
                "habits_done": habit_done[d],
                "focus_minutes": time_selectors.tracked_seconds(user, b.start, b.end, focus_only=True) // 60,
                "tracked_minutes": time_selectors.tracked_seconds(user, b.start, b.end) // 60,
            }
        )
    return series


def wellness_metrics(user: User, w: Window) -> dict[str, Any]:
    from apps.wellness.selectors import summary

    return summary(user, w.first, w.last)


def summary(user: User, period: Period, anchor: date, *, compare: bool = True) -> dict[str, Any]:
    w = window(user, period, anchor)
    result: dict[str, Any] = {
        "period": period,
        "from": w.first.isoformat(),
        "to": w.last.isoformat(),
        "formula_version": FORMULA_VERSION,
        "is_final": w.is_final,
        "tasks": task_metrics(user, w),
        "habits": habit_metrics(user, w),
        "time": time_metrics(user, w),
        "goals": goal_metrics(user, w),
        "wellness": wellness_metrics(user, w),
        "series": daily_series(user, w) if period != "day" else [],
    }
    if compare:
        p = previous(user, w)
        result["previous"] = {
            "from": p.first.isoformat(),
            "to": p.last.isoformat(),
            "task_completion_rate": task_metrics(user, p)["completion_rate"]["value"],
            "habit_consistency": habit_metrics(user, p)["consistency"]["value"],
            "focus_hours": time_metrics(user, p)["focus_hours"]["value"],
        }
    return result


def has_any_data(user: User, w: Window) -> bool:
    return (
        Task.objects.filter(user=user).filter(Q(created_at__lt=w.end)).exists()
        or HabitLog.objects.filter(user=user, log_date__lte=w.last).exists()
    )
