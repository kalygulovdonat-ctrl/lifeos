"""dashboard_for_date: one aggregated read across modules (SDD §6.2, DASH-001…009)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from apps.accounts.models import User
from apps.schedule import selectors as schedule
from apps.schedule.models import EventStatus, TimeType
from apps.tasks import selectors as tasks
from common.time import now, period_bounds

UPCOMING_LIMIT = 5


@dataclass
class Dashboard:
    day: date
    events: list[schedule.EventView]
    upcoming: list[schedule.EventView]
    day_tasks: tasks.DayTasks
    inbox_count: int
    free: schedule.FreeTime
    planned_minutes: int
    focus_minutes: int


def dashboard_for_date(user: User, day: date) -> Dashboard:
    tz = user.profile.timezone
    bounds = period_bounds(tz, "day", day)
    events = schedule.events_in_range(user, bounds.start, bounds.end)
    active = [e for e in events if e.status != EventStatus.CANCELLED]
    moment = now()
    upcoming = [
        e
        for e in schedule.events_in_range(user, moment, moment + timedelta(days=7), include_cancelled=False)
        if e.start_at >= moment
    ][:UPCOMING_LIMIT]

    def minutes(items: list[schedule.EventView]) -> int:
        return sum(
            int((min(e.end_at, bounds.end) - max(e.start_at, bounds.start)).total_seconds() // 60)
            for e in items
        )

    return Dashboard(
        day=day,
        events=events,
        upcoming=upcoming,
        day_tasks=tasks.tasks_for_day(user, day),
        inbox_count=tasks.inbox_count(user),
        free=schedule.free_time(user, day),
        planned_minutes=minutes([e for e in active if e.time_type != TimeType.FREE]),
        focus_minutes=minutes([e for e in active if e.time_type == TimeType.FOCUS]),
    )
