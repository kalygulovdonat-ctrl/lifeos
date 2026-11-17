"""Write side of habits (SDD §4.6, BR-030…BR-037)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction

from apps.accounts.models import Category, User
from apps.habits import logic
from apps.habits.models import (
    NON_DONE,
    PERIOD_FREQUENCIES,
    VALUE_TYPES,
    FrequencyType,
    Habit,
    HabitLog,
    HabitLogRevision,
    HabitPause,
    HabitSchedule,
    LogSource,
    LogStatus,
    TrackingType,
)
from common.audit import audit, diff
from common.exceptions import ConflictError, DomainValidationError
from common.time import local_today

HABIT_FIELDS = {
    "name",
    "description",
    "category",
    "tracking_type",
    "unit",
    "scale_min",
    "scale_max",
    "preferred_time",
    "start_date",
    "end_date",
    "reminder_time",
    "color",
    "icon",
    "is_active",
    "sort_order",
}
SCHEDULE_FIELDS = (
    "frequency_type",
    "weekdays_mask",
    "times_per_period",
    "interval_days",
    "target_value",
    "target_comparison",
)


def _invalid(field: str, message: str) -> DomainValidationError:
    return DomainValidationError(details={field: [message]})


def _validate_habit(user: User, h: dict[str, Any]) -> None:
    if not str(h.get("name", "")).strip():
        raise _invalid("name", "Name must not be blank.")
    category: Category | None = h.get("category")
    if category is not None and category.user_id != user.id:
        raise _invalid("category_id", "Unknown category.")
    if h.get("tracking_type") == TrackingType.SCALE:
        lo, hi = h.get("scale_min"), h.get("scale_max")
        if lo is None or hi is None or hi <= lo:
            raise _invalid("scale_max", "A scale needs scale_min < scale_max.")
    if h.get("tracking_type") == TrackingType.DURATION:
        h["unit"] = "min"
    end, start = h.get("end_date"), h.get("start_date")
    if end and start and end < start:
        raise _invalid("end_date", "Must not be before start_date.")


def _validate_schedule(tracking_type: str, s: dict[str, Any]) -> dict[str, Any]:
    s = {k: s.get(k) for k in SCHEDULE_FIELDS}
    freq = s["frequency_type"] or FrequencyType.DAILY
    s["frequency_type"] = freq
    s["target_comparison"] = s["target_comparison"] or "GTE"
    if freq == FrequencyType.WEEKDAYS and not (s["weekdays_mask"] and 1 <= s["weekdays_mask"] <= 127):
        raise _invalid("weekdays_mask", "Pick at least one weekday.")
    if freq in PERIOD_FREQUENCIES:
        limit = 7 if freq == FrequencyType.TIMES_PER_WEEK else 31
        if not s["times_per_period"] or not 1 <= s["times_per_period"] <= limit:
            raise _invalid("times_per_period", f"Must be 1..{limit}.")
    if freq == FrequencyType.EVERY_N_DAYS and not (s["interval_days"] and 2 <= s["interval_days"] <= 365):
        raise _invalid("interval_days", "Must be 2..365.")
    for key, needed in (
        ("weekdays_mask", FrequencyType.WEEKDAYS),
        ("interval_days", FrequencyType.EVERY_N_DAYS),
    ):
        if freq != needed:
            s[key] = None
    if freq not in PERIOD_FREQUENCIES:
        s["times_per_period"] = None
    target = s["target_value"]
    if tracking_type == TrackingType.BOOLEAN:
        s["target_value"] = None
    elif tracking_type in VALUE_TYPES and (target is None or target <= 0):
        raise _invalid("target_value", "A positive target is required.")
    return s


@transaction.atomic
def habit_create(*, user: User, data: dict[str, Any], schedule: dict[str, Any]) -> Habit:
    h = {k: v for k, v in data.items() if k in HABIT_FIELDS}
    h.setdefault("start_date", local_today(user.profile.timezone))
    h.setdefault("tracking_type", TrackingType.BOOLEAN)
    _validate_habit(user, h)
    s = _validate_schedule(h["tracking_type"], schedule)
    if h["tracking_type"] == TrackingType.SCALE and s["target_value"] is not None:
        if not h["scale_min"] <= s["target_value"] <= h["scale_max"]:
            raise _invalid("target_value", "Must be inside the scale.")
    h["name"] = h["name"].strip()
    habit = Habit.objects.create(user=user, **h)
    HabitSchedule.objects.create(user=user, habit=habit, valid_from=habit.start_date, **s)
    audit(user=user, entity_type="habit", entity_id=habit.id, action="CREATE")
    return habit


@transaction.atomic
def habit_update(
    *, user: User, habit: Habit, data: dict[str, Any], schedule: dict[str, Any] | None = None
) -> Habit:
    habit = Habit.objects.select_for_update().get(pk=habit.pk, user=user)
    h = {k: v for k, v in data.items() if k in HABIT_FIELDS}
    if "tracking_type" in h and h["tracking_type"] != habit.tracking_type:
        if HabitLog.objects.filter(habit=habit).exists():
            raise ConflictError(
                "The tracking type cannot change once the habit has logs (BR-031).", code="HABIT_TYPE_LOCKED"
            )
    merged = {f: getattr(habit, f) for f in HABIT_FIELDS} | h
    _validate_habit(user, merged)
    if "unit" in merged and merged["tracking_type"] == TrackingType.DURATION:
        h["unit"] = "min"
    changes = diff(habit, h)
    for k, v in h.items():
        setattr(habit, k, v.strip() if k == "name" else v)
    habit.save()
    if schedule is not None:
        _new_schedule_version(user, habit, _validate_schedule(habit.tracking_type, schedule))
    if changes or schedule is not None:
        audit(user=user, entity_type="habit", entity_id=habit.id, action="UPDATE", changes=changes)
    return habit


def _new_schedule_version(user: User, habit: Habit, s: dict[str, Any]) -> None:
    """Frequency changes never rewrite history (HAB-005, ADR-010)."""
    today = local_today(user.profile.timezone)
    current = HabitSchedule.objects.filter(habit=habit, valid_to__isnull=True).first()
    if current is not None and all(getattr(current, k) == v for k, v in s.items()):
        return
    if current is not None and current.valid_from >= today:
        for k, v in s.items():
            setattr(current, k, v)
        current.save()
        return
    if current is not None:
        current.valid_to = today - timedelta(days=1)
        current.save(update_fields=["valid_to", "updated_at"])
    HabitSchedule.objects.create(user=user, habit=habit, valid_from=max(today, habit.start_date), **s)


def habit_set_archived(*, user: User, habit: Habit, archived: bool) -> Habit:
    habit.is_archived = archived
    habit.save(update_fields=["is_archived", "updated_at"])
    audit(user=user, entity_type="habit", entity_id=habit.id, action="ARCHIVE" if archived else "RESTORE")
    return habit


# ---------------------------------------------------------------- logs


def _recompute_day(habit: Habit, day: date) -> None:
    """DURATION/QUANTITY: the day's status follows the sum of its records (BR-036)."""
    if habit.tracking_type not in VALUE_TYPES and habit.tracking_type != TrackingType.SCALE:
        return
    logs = list(
        HabitLog.objects.filter(habit=habit, log_date=day, is_voided=False).exclude(status__in=NON_DONE)
    )
    if not logs:
        return
    sched = logic.schedule_on(list(habit.schedules.order_by("valid_from")), day)
    status = logic.summarize_day(logs, habit.tracking_type, sched).status
    HabitLog.objects.filter(id__in=[log.id for log in logs]).exclude(status=status).update(status=status)


@transaction.atomic
def habit_log_create(
    *,
    user: User,
    habit: Habit,
    log_date: date,
    status: str = LogStatus.DONE,
    value: Decimal | None = None,
    note: str = "",
    source: str = LogSource.MANUAL,
) -> HabitLog:
    habit = Habit.objects.select_for_update().get(pk=habit.pk, user=user)
    tz = user.profile.timezone
    if log_date > local_today(tz):
        raise _invalid("log_date", "Cannot log a future day.")
    if not logic.in_lifetime(habit, log_date):
        raise _invalid("log_date", "Outside the habit's active dates.")
    if habit.is_archived:
        raise _invalid("habit", "The habit is archived.")
    if status == LogStatus.PARTIAL:
        status = LogStatus.DONE  # the server decides DONE vs PARTIAL from the value

    tt = habit.tracking_type
    if status in NON_DONE:
        value = None
    elif tt == TrackingType.BOOLEAN:
        value = None
    elif value is None:
        raise _invalid("value", "A value is required for this habit.")
    elif tt == TrackingType.SCALE and not habit.scale_min <= value <= habit.scale_max:
        raise _invalid("value", f"Must be between {habit.scale_min} and {habit.scale_max}.")
    elif tt in VALUE_TYPES and value <= 0:
        raise _invalid("value", "Must be greater than zero.")

    existing = list(HabitLog.objects.filter(habit=habit, log_date=log_date, is_voided=False))
    if existing and (
        status in NON_DONE
        or any(e.status in NON_DONE for e in existing)
        or tt in (TrackingType.BOOLEAN, TrackingType.SCALE)
    ):
        raise ConflictError("This day already has a record.", code="HABIT_ALREADY_LOGGED")

    sched = logic.schedule_on(list(habit.schedules.order_by("valid_from")), log_date)
    try:
        log = HabitLog.objects.create(
            user=user,
            habit=habit,
            log_date=log_date,
            timezone=tz,
            status=status,
            value=value,
            note=note.strip(),
            tracking_type_snapshot=tt,
            target_value_snapshot=sched.target_value if sched else None,
            unit_snapshot=habit.unit,
            source=source,
        )
    except IntegrityError as exc:  # concurrent duplicate
        raise ConflictError("This day already has a record.", code="HABIT_ALREADY_LOGGED") from exc
    _recompute_day(habit, log_date)
    log.refresh_from_db()
    return log


def _snapshot(log: HabitLog) -> dict[str, Any]:
    return {
        "status": log.status,
        "value": str(log.value) if log.value is not None else None,
        "note": log.note,
        "is_voided": log.is_voided,
    }


@transaction.atomic
def habit_log_update(*, user: User, log: HabitLog, data: dict[str, Any]) -> HabitLog:
    if log.is_voided:
        raise ConflictError("A voided record cannot be edited.", code="HABIT_LOG_VOIDED")
    before = _snapshot(log)
    habit = log.habit
    if "value" in data and log.status not in NON_DONE and habit.tracking_type != TrackingType.BOOLEAN:
        value = data["value"]
        if value is None or (habit.tracking_type in VALUE_TYPES and value <= 0):
            raise _invalid("value", "Must be greater than zero.")
        if habit.tracking_type == TrackingType.SCALE and not habit.scale_min <= value <= habit.scale_max:
            raise _invalid("value", f"Must be between {habit.scale_min} and {habit.scale_max}.")
        log.value = value
    if "note" in data:
        log.note = data["note"].strip()
    log.save()
    _recompute_day(habit, log.log_date)
    log.refresh_from_db()
    HabitLogRevision.objects.create(user=user, habit_log=log, old_values=before, new_values=_snapshot(log))
    return log


@transaction.atomic
def habit_log_void(*, user: User, log: HabitLog) -> HabitLog:
    """DELETE = void: the record stays for history (PRD §6.4)."""
    if log.is_voided:
        return log
    before = _snapshot(log)
    log.is_voided = True
    log.save(update_fields=["is_voided", "updated_at"])
    _recompute_day(log.habit, log.log_date)
    HabitLogRevision.objects.create(user=user, habit_log=log, old_values=before, new_values=_snapshot(log))
    return log


# ---------------------------------------------------------------- pauses


def habit_pause_create(
    *, user: User, habit: Habit, start_date: date, end_date: date | None = None, reason: str = ""
) -> HabitPause:
    if end_date and end_date < start_date:
        raise _invalid("end_date", "Must not be before start_date.")
    for p in HabitPause.objects.filter(habit=habit):
        p_end = p.end_date or date.max
        if start_date <= p_end and p.start_date <= (end_date or date.max):
            raise _invalid("start_date", "Overlaps another pause.")
    return HabitPause.objects.create(
        user=user, habit=habit, start_date=start_date, end_date=end_date, reason=reason.strip()
    )


def habit_pause_delete(*, user: User, pause: HabitPause) -> None:
    pause.delete()
