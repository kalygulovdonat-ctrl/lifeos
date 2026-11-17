"""Read side of habits. Every function takes the owner first (BR-002)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db.models import Prefetch, QuerySet

from apps.accounts.models import User
from apps.habits import logic
from apps.habits.models import PERIOD_FREQUENCIES, Habit, HabitLog, HabitPause, HabitSchedule
from common.exceptions import NotFoundError
from common.time import local_today


def _with_relations(qs: QuerySet[Habit]) -> QuerySet[Habit]:
    return qs.select_related("category").prefetch_related(
        Prefetch("schedules", queryset=HabitSchedule.objects.order_by("valid_from")),
        Prefetch("pauses", queryset=HabitPause.objects.order_by("start_date")),
    )


def habit_list(user: User, *, archived: bool = False) -> QuerySet[Habit]:
    return _with_relations(Habit.objects.filter(user=user, is_archived=archived))


def habit_get(user: User, habit_id: UUID | str) -> Habit:
    try:
        return _with_relations(Habit.objects.filter(user=user)).get(id=habit_id)
    except (Habit.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def current_schedule(habit: Habit) -> HabitSchedule | None:
    items = list(habit.schedules.all())
    return next((s for s in items if s.valid_to is None), items[-1] if items else None)


def log_get(user: User, log_id: UUID | str) -> HabitLog:
    try:
        return HabitLog.objects.select_related("habit").get(user=user, id=log_id)
    except (HabitLog.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def pause_get(user: User, pause_id: UUID | str) -> HabitPause:
    try:
        return HabitPause.objects.select_related("habit").get(user=user, id=pause_id)
    except (HabitPause.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def logs_between(user: User, habit: Habit, first: date, last: date) -> list[HabitLog]:
    return list(HabitLog.objects.filter(user=user, habit=habit, log_date__gte=first, log_date__lte=last))


def all_logs(user: User, habit: Habit) -> list[HabitLog]:
    return list(HabitLog.objects.filter(user=user, habit=habit, is_voided=False))


@dataclass
class TodayItem:
    habit: Habit
    schedule: HabitSchedule | None
    planned: bool
    paused: bool
    status: str | None
    value: Decimal | None
    log_ids: list[Any]
    period_done: int | None
    period_needed: int | None
    current_streak: int


def habits_for_day(user: User, day: date | None = None) -> list[TodayItem]:
    profile = user.profile
    day = day or local_today(profile.timezone)
    today = local_today(profile.timezone)
    items: list[TodayItem] = []
    for habit in habit_list(user):
        if not habit.is_active or not logic.in_lifetime(habit, day):
            continue
        schedules = list(habit.schedules.all())
        pauses = list(habit.pauses.all())
        sched = logic.schedule_on(schedules, day)
        logs = all_logs(user, habit)
        summary = logic.summarize_day(
            [log for log in logs if log.log_date == day], habit.tracking_type, sched
        )
        period_done = period_needed = None
        if sched is not None and sched.frequency_type in PERIOD_FREQUENCIES:
            start = logic.period_start(day, sched.frequency_type, profile.week_start)
            unit = logic.units(habit, schedules, pauses, logs, start, start, today, profile.week_start)
            if unit:
                period_done, period_needed = unit[0].done, unit[0].needed
        history = logic.units(
            habit, schedules, pauses, logs, habit.start_date, today, today, profile.week_start
        )
        current, _ = logic.streaks(history)
        items.append(
            TodayItem(
                habit=habit,
                schedule=sched,
                planned=logic.is_planned_day(habit, sched, day),
                paused=logic.is_paused(pauses, day),
                status=summary.status,
                value=summary.value,
                log_ids=summary.log_ids,
                period_done=period_done,
                period_needed=period_needed,
                current_streak=current,
            )
        )
    return items


def habit_stats(user: User, habit: Habit, period: str) -> logic.Stats:
    profile = user.profile
    today = local_today(profile.timezone)
    if period == "month":
        first = today.replace(day=1)
    elif period == "year":
        first = today.replace(month=1, day=1)
    else:
        first = today - timedelta(days=(today.isoweekday() - profile.week_start) % 7)
    return logic.compute_stats(
        habit,
        list(habit.schedules.all()),
        list(habit.pauses.all()),
        all_logs(user, habit),
        first,
        today,
        today,
        profile.week_start,
    )


def habit_history(user: User, habit: Habit, first: date, last: date) -> list[dict[str, Any]]:
    """Per-day results for a range (heatmap, history list)."""
    schedules = list(habit.schedules.all())
    pauses = list(habit.pauses.all())
    by_day = logic.logs_by_day(logs_between(user, habit, first, last))
    days: list[dict[str, Any]] = []
    day = first
    while day <= last:
        sched = logic.schedule_on(schedules, day)
        summary = logic.summarize_day(by_day.get(day, []), habit.tracking_type, sched)
        days.append(
            {
                "date": day,
                "planned": logic.is_planned_day(habit, sched, day),
                "paused": logic.is_paused(pauses, day),
                "status": summary.status,
                "value": summary.value,
            }
        )
        day += timedelta(days=1)
    return days
