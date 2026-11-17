"""Pure habit maths (SDD §5.3, §5.4) on plain objects, no database."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import count

from apps.habits import logic

_ids = count()


@dataclass
class H:
    tracking_type: str = "BOOLEAN"
    start_date: date = date(2026, 11, 2)  # Monday
    end_date: date | None = None


@dataclass
class S:
    valid_from: date = date(2026, 11, 2)
    valid_to: date | None = None
    frequency_type: str = "DAILY"
    weekdays_mask: int | None = None
    times_per_period: int | None = None
    interval_days: int | None = None
    target_value: Decimal | None = None
    target_comparison: str = "GTE"


@dataclass
class L:
    log_date: date
    status: str = "DONE"
    value: Decimal | None = None
    is_voided: bool = False
    id: int = 0

    def __post_init__(self):
        self.id = next(_ids)


@dataclass
class P:
    start_date: date
    end_date: date | None = None


D = date(2026, 11, 2)


def day(n):
    return D + timedelta(days=n)


def stats(habit, schedules, logs, today, pauses=(), first=None, last=None):
    return logic.compute_stats(habit, schedules, list(pauses), logs, first or D, last or today, today)


def test_daily_consistency_excludes_today_and_rest():
    logs = [L(day(0)), L(day(1)), L(day(2), "REST"), L(day(3), "SKIPPED")]
    s = stats(H(), [S()], logs, today=day(5))
    # eligible: days 0..4 (today=day5 not final), REST excluded -> 4 units, 2 success
    assert (s.success, s.eligible) == (2, 4)
    assert s.consistency == 0.5


def test_streak_rest_and_pause_do_not_break():
    logs = [L(day(0)), L(day(1), "REST"), L(day(3)), L(day(4))]
    s = stats(H(), [S()], logs, today=day(5), pauses=[P(day(2), day(2))])
    assert (s.current_streak, s.best_streak) == (3, 3)


def test_missed_day_breaks_streak_today_counts_only_when_done():
    logs = [L(day(0)), L(day(1)), L(day(3))]
    s = stats(H(), [S()], logs, today=day(4))
    assert (s.current_streak, s.best_streak) == (1, 2)
    s = stats(H(), [S()], [*logs, L(day(4))], today=day(4))
    assert s.current_streak == 2


def test_weekdays_mask_only_counts_planned_days():
    sched = S(frequency_type="WEEKDAYS", weekdays_mask=0b0000101)  # Mon + Wed
    logs = [L(day(0)), L(day(2))]
    s = stats(H(), [sched], logs, today=day(7))
    assert (s.success, s.eligible, s.current_streak) == (2, 2, 2)


def test_every_n_days():
    sched = S(frequency_type="EVERY_N_DAYS", interval_days=3)
    habit = H()
    planned = [d for d in range(10) if logic.is_planned_day(habit, sched, day(d))]
    assert planned == [0, 3, 6, 9]


def test_times_per_week_is_period_based():
    sched = S(frequency_type="TIMES_PER_WEEK", times_per_period=3)
    week1 = [L(day(0)), L(day(2)), L(day(4))]  # success
    week2 = [L(day(7))]  # fail
    s = stats(H(), [sched], week1 + week2, today=day(16))
    assert (s.success, s.eligible) == (1, 2)
    assert (s.current_streak, s.best_streak) == (0, 1)


def test_quantity_sums_and_lte_targets():
    habit = H(tracking_type="QUANTITY")
    sched = S(target_value=Decimal(8))
    logs = [L(day(0), value=Decimal(5)), L(day(0), value=Decimal(4))]
    assert logic.summarize_day(logs, habit.tracking_type, sched).status == "DONE"
    assert logic.summarize_day(logs[:1], habit.tracking_type, sched).status == "PARTIAL"
    screen = S(target_value=Decimal(60), target_comparison="LTE")
    assert logic.summarize_day([L(day(0), value=Decimal(45))], "DURATION", screen).status == "DONE"
    assert logic.summarize_day([L(day(0), value=Decimal(90))], "DURATION", screen).status == "PARTIAL"


def test_schedule_versions_apply_per_day():
    old = S(valid_to=day(6), frequency_type="DAILY")
    new = S(valid_from=day(7), frequency_type="WEEKDAYS", weekdays_mask=1)  # Mondays only
    logs = [L(day(n)) for n in range(7)] + [L(day(7))]
    s = stats(H(), [old, new], logs, today=day(15))
    # 7 daily successes, then Monday day(7) under the new version = 8; Monday day(14) is missed
    assert s.best_streak == 8
    assert s.current_streak == 0


def test_voided_logs_are_ignored_and_no_data_is_none():
    s = stats(H(), [S()], [L(day(0), is_voided=True)], today=day(0))
    assert s.consistency is None
    assert s.done_days == 0
