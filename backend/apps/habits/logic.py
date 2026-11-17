"""Pure habit maths (SDD §5.3, §5.4): no database access, fully unit-tested.

Inputs are plain model instances already loaded by a selector; everything works on local
dates (the log_date of each record), never on "now".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.habits.models import (
    NON_DONE,
    VALUE_TYPES,
    Comparison,
    FrequencyType,
    LogStatus,
    TrackingType,
)


def schedule_on(schedules: Sequence[Any], day: date) -> Any | None:
    for s in schedules:
        if s.valid_from <= day and (s.valid_to is None or day <= s.valid_to):
            return s
    return None


def is_paused(pauses: Iterable[Any], day: date) -> bool:
    return any(p.start_date <= day and (p.end_date is None or day <= p.end_date) for p in pauses)


def in_lifetime(habit: Any, day: date) -> bool:
    return day >= habit.start_date and (habit.end_date is None or day <= habit.end_date)


def is_planned_day(habit: Any, schedule: Any | None, day: date) -> bool:
    """Whether `day` is a scheduled day under the version in force (period types: every day counts)."""
    if schedule is None or not in_lifetime(habit, day):
        return False
    freq = schedule.frequency_type
    if freq == FrequencyType.WEEKDAYS:
        return bool((schedule.weekdays_mask or 0) & (1 << (day.isoweekday() - 1)))
    if freq == FrequencyType.EVERY_N_DAYS:
        anchor = max(schedule.valid_from, habit.start_date)
        return (day - anchor).days % (schedule.interval_days or 1) == 0
    return True


def meets_target(value: Decimal | None, target: Decimal | None, comparison: str) -> bool:
    if target is None:
        return value is not None
    if value is None:
        return False
    return value <= target if comparison == Comparison.LTE else value >= target


@dataclass
class DaySummary:
    status: str | None  # None = nothing logged
    value: Decimal | None
    log_ids: list[Any] = field(default_factory=list)


def summarize_day(logs: Sequence[Any], tracking_type: str, schedule: Any | None) -> DaySummary:
    """Daily result from the non-voided logs of one day (BR-036)."""
    if not logs:
        return DaySummary(None, None)
    ids = [log.id for log in logs]
    skip = next((log for log in logs if log.status in NON_DONE), None)
    if skip is not None:
        return DaySummary(skip.status, None, ids)
    target = schedule.target_value if schedule else None
    comparison = schedule.target_comparison if schedule else Comparison.GTE
    if tracking_type == TrackingType.BOOLEAN:
        return DaySummary(LogStatus.DONE, None, ids)
    if tracking_type in VALUE_TYPES:
        total = sum((log.value or Decimal(0) for log in logs), Decimal(0))
        ok = meets_target(total, target, comparison)
        return DaySummary(LogStatus.DONE if ok else LogStatus.PARTIAL, total, ids)
    value = logs[-1].value  # SCALE: one record per day
    ok = meets_target(value, target, comparison)
    return DaySummary(LogStatus.DONE if ok else LogStatus.PARTIAL, value, ids)


def logs_by_day(logs: Iterable[Any]) -> dict[date, list[Any]]:
    grouped: dict[date, list[Any]] = defaultdict(list)
    for log in logs:
        if not log.is_voided:
            grouped[log.log_date].append(log)
    return grouped


def period_start(day: date, freq: str, week_start: int) -> date:
    if freq == FrequencyType.TIMES_PER_MONTH:
        return day.replace(day=1)
    return day - timedelta(days=(day.isoweekday() - week_start) % 7)


def period_end(start: date, freq: str) -> date:
    if freq == FrequencyType.TIMES_PER_MONTH:
        return (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return start + timedelta(days=6)


@dataclass
class Unit:
    """One scheduled unit (a day, or a week/month for TIMES_PER_* habits)."""

    start: date
    end: date
    outcome: str  # "success" | "fail" | "rest" | "open" (current, not final yet)
    done: int = 0
    needed: int = 1


def units(
    habit: Any,
    schedules: Sequence[Any],
    pauses: Sequence[Any],
    logs: Iterable[Any],
    first: date,
    last: date,
    today: date,
    week_start: int = 1,
) -> list[Unit]:
    """Scheduled units overlapping [first, last], each with its outcome."""
    by_day = logs_by_day(logs)
    first = max(first, habit.start_date)
    if habit.end_date:
        last = min(last, habit.end_date)
    result: list[Unit] = []
    day = first
    while day <= last:
        sched = schedule_on(schedules, day)
        if sched is None:
            day += timedelta(days=1)
            continue
        freq = sched.frequency_type
        if freq in (FrequencyType.TIMES_PER_WEEK, FrequencyType.TIMES_PER_MONTH):
            start = period_start(day, freq, week_start)
            end = period_end(start, freq)
            days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
            active = [d for d in days if in_lifetime(habit, d) and not is_paused(pauses, d)]
            done = sum(
                1
                for d in active
                if summarize_day(by_day.get(d, []), habit.tracking_type, schedule_on(schedules, d)).status
                == LogStatus.DONE
            )
            needed = sched.times_per_period or 1
            if not active:
                outcome = "rest"
            elif done >= needed:
                outcome = "success"
            elif end >= today:
                outcome = "open"
            else:
                outcome = "fail"
            result.append(Unit(start, end, outcome, done, needed))
            day = end + timedelta(days=1)
            continue

        if is_planned_day(habit, sched, day) and not is_paused(pauses, day):
            summary = summarize_day(by_day.get(day, []), habit.tracking_type, sched)
            if summary.status == LogStatus.DONE:
                outcome = "success"
            elif summary.status == LogStatus.REST:
                outcome = "rest"
            elif day >= today:
                outcome = "open"  # today is not final until it is done (BR-061)
            else:
                outcome = "fail"
            result.append(Unit(day, day, outcome, int(outcome == "success"), 1))
        day += timedelta(days=1)
    return result


@dataclass
class Stats:
    consistency: float | None  # None = no eligible units yet
    success: int
    eligible: int
    current_streak: int
    best_streak: int
    total_value: Decimal
    done_days: int


def streaks(all_units: Sequence[Unit]) -> tuple[int, int]:
    """(current, best): rest/paused units are skipped, a failure breaks the run (BR-037)."""
    best = run = 0
    for unit in all_units:
        if unit.outcome == "success":
            run += 1
            best = max(best, run)
        elif unit.outcome == "fail":
            run = 0
    # An open (current) unit that is not done yet does not break the current streak.
    return run, best


def compute_stats(
    habit: Any,
    schedules: Sequence[Any],
    pauses: Sequence[Any],
    logs: Sequence[Any],
    first: date,
    last: date,
    today: date,
    week_start: int = 1,
) -> Stats:
    period_units = units(habit, schedules, pauses, logs, first, last, today, week_start)
    final = [u for u in period_units if u.outcome in ("success", "fail")]
    success = sum(1 for u in final if u.outcome == "success")
    history = units(habit, schedules, pauses, logs, habit.start_date, today, today, week_start)
    current, best = streaks(history)
    by_day = logs_by_day(logs)
    in_range = [log for d, items in by_day.items() if first <= d <= last for log in items]
    total = sum((log.value or Decimal(0) for log in in_range if log.status not in NON_DONE), Decimal(0))
    done_days = sum(
        1
        for d, items in by_day.items()
        if first <= d <= last
        and summarize_day(items, habit.tracking_type, schedule_on(schedules, d)).status == LogStatus.DONE
    )
    return Stats(
        consistency=(success / len(final)) if final else None,
        success=success,
        eligible=len(final),
        current_streak=current,
        best_streak=best,
        total_value=total,
        done_days=done_days,
    )
