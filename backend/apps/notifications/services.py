"""Notifications and reminder dispatch (SDD §4.13).

Reminders are created lazily: every minute the dispatcher looks at what is due soon (events,
series occurrences, habits) and inserts one Reminder per target and moment — the unique key
makes the job idempotent, so a missed or repeated run never notifies twice.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.notifications.models import Notification, Reminder, ReminderStatus, TargetType
from common.time import local_today, now

LOOKAHEAD = timedelta(days=1)
GRACE = timedelta(minutes=30)  # a reminder older than this is skipped instead of sent late


def notification_create(
    *,
    user: User,
    type: str,
    message_key: str,
    params: dict[str, Any] | None = None,
    link: str = "",
    reminder: Reminder | None = None,
) -> Notification:
    return Notification.objects.create(
        user=user, type=type, message_key=message_key, params=params or {}, link=link, reminder=reminder
    )


def mark_read(*, user: User, notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = now()
        notification.save(update_fields=["read_at", "updated_at"])
    return notification


def mark_all_read(*, user: User) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).update(read_at=now())


def _fire(
    user: User,
    target_type: str,
    target_id: Any,
    remind_at: datetime,
    message_key: str,
    params: dict[str, Any],
    link: str,
) -> bool:
    """Insert the reminder + notification once; False when it already exists."""
    try:
        with transaction.atomic():
            reminder = Reminder.objects.create(
                user=user,
                target_type=target_type,
                target_id=target_id,
                remind_at=remind_at,
                status=ReminderStatus.SENT,
                sent_at=now(),
            )
            notification_create(
                user=user,
                type="REMINDER",
                message_key=message_key,
                params=params,
                link=link,
                reminder=reminder,
            )
    except IntegrityError:
        return False
    return True


def event_reminders(moment: datetime) -> int:
    from apps.schedule.models import Event, EventSeries
    from apps.schedule.selectors import events_in_range

    sent = 0
    users = set(
        Event.objects.filter(
            reminder_minutes__isnull=False, start_at__gte=moment, start_at__lt=moment + LOOKAHEAD
        ).values_list("user_id", flat=True)
    ) | set(
        EventSeries.objects.filter(reminder_minutes__isnull=False, is_active=True).values_list(
            "user_id", flat=True
        )
    )
    for user in User.objects.filter(id__in=users, is_active=True).select_related("profile"):
        for ev in events_in_range(user, moment - GRACE, moment + LOOKAHEAD, include_cancelled=False):
            if ev.reminder_minutes is None or ev.start_at < moment:
                continue
            remind_at = ev.start_at - timedelta(minutes=ev.reminder_minutes)
            if not (moment - GRACE <= remind_at <= moment):
                continue
            target = ev.id or ev.series_id
            sent += _fire(
                user,
                TargetType.EVENT,
                target,
                remind_at,
                "event",
                {"title": ev.title, "start_at": ev.start_at.isoformat(), "minutes": ev.reminder_minutes},
                "/schedule/day",
            )
    return sent


def habit_reminders(moment: datetime) -> int:
    from apps.habits import logic
    from apps.habits.models import Habit, HabitLog

    sent = 0
    habits = (
        Habit.objects.filter(reminder_time__isnull=False, is_active=True, is_archived=False)
        .select_related("user__profile")
        .prefetch_related("schedules", "pauses")
    )
    for habit in habits:
        tz = habit.user.profile.timezone
        today = local_today(tz)
        remind_at = datetime.combine(today, habit.reminder_time, tzinfo=ZoneInfo(tz))
        if not (moment - GRACE <= remind_at <= moment):
            continue
        sched = logic.schedule_on(list(habit.schedules.all()), today)
        if not logic.is_planned_day(habit, sched, today) or logic.is_paused(habit.pauses.all(), today):
            continue
        if HabitLog.objects.filter(habit=habit, log_date=today, is_voided=False).exists():
            continue
        sent += _fire(
            habit.user, TargetType.HABIT, habit.id, remind_at, "habit", {"name": habit.name}, "/habits"
        )
    return sent


def dispatch_due(moment: datetime | None = None) -> int:
    moment = moment or now()
    return event_reminders(moment) + habit_reminders(moment)
