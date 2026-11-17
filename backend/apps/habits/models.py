"""Habits (SDD §4.6): versioned frequency, immutable logs with snapshots (ADR-010, ADR-011)."""

from __future__ import annotations

from django.db import models
from django.db.models import F, Q

from apps.accounts.models import HEX_COLOR, Category
from common.models import OwnedModel, choices_check


class TrackingType(models.TextChoices):
    BOOLEAN = "BOOLEAN"
    DURATION = "DURATION"
    QUANTITY = "QUANTITY"
    SCALE = "SCALE"


VALUE_TYPES = (TrackingType.DURATION, TrackingType.QUANTITY)


class FrequencyType(models.TextChoices):
    DAILY = "DAILY"
    WEEKDAYS = "WEEKDAYS"
    TIMES_PER_WEEK = "TIMES_PER_WEEK"
    TIMES_PER_MONTH = "TIMES_PER_MONTH"
    EVERY_N_DAYS = "EVERY_N_DAYS"


PERIOD_FREQUENCIES = (FrequencyType.TIMES_PER_WEEK, FrequencyType.TIMES_PER_MONTH)


class Comparison(models.TextChoices):
    GTE = "GTE"
    LTE = "LTE"


class LogStatus(models.TextChoices):
    DONE = "DONE"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"
    REST = "REST"
    MISSED = "MISSED"


NON_DONE = (LogStatus.SKIPPED, LogStatus.REST, LogStatus.MISSED)


class LogSource(models.TextChoices):
    MANUAL = "MANUAL"
    TIMER = "TIMER"
    AI = "AI"
    IMPORT = "IMPORT"


class Habit(OwnedModel):
    name = models.CharField(max_length=120)
    description = models.TextField(default="", blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    tracking_type = models.CharField(max_length=8, choices=TrackingType.choices, default=TrackingType.BOOLEAN)
    unit = models.CharField(max_length=20, default="", blank=True)
    scale_min = models.SmallIntegerField(null=True, blank=True)
    scale_max = models.SmallIntegerField(null=True, blank=True)
    preferred_time = models.TimeField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    reminder_time = models.TimeField(null=True, blank=True)
    color = models.CharField(max_length=7, null=True, blank=True, validators=[HEX_COLOR])
    icon = models.CharField(max_length=40, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "habit"
        ordering = ["sort_order", "created_at"]
        constraints = [
            choices_check("tracking_type", TrackingType, "habit_tracking_type_ck"),
            models.CheckConstraint(
                condition=~Q(tracking_type=TrackingType.SCALE)
                | Q(scale_min__isnull=False, scale_max__isnull=False, scale_max__gt=F("scale_min")),
                name="habit_scale_bounds_ck",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="habit_end_after_start_ck",
            ),
        ]
        indexes = [models.Index(fields=["user", "is_archived"], name="habit_user_archived_ix")]

    def __str__(self) -> str:
        return self.name


class HabitSchedule(OwnedModel):
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name="schedules")
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)  # inclusive; NULL = current version
    frequency_type = models.CharField(
        max_length=16, choices=FrequencyType.choices, default=FrequencyType.DAILY
    )
    weekdays_mask = models.SmallIntegerField(null=True, blank=True)  # bit 0 = Monday
    times_per_period = models.SmallIntegerField(null=True, blank=True)
    interval_days = models.SmallIntegerField(null=True, blank=True)
    target_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_comparison = models.CharField(max_length=3, choices=Comparison.choices, default=Comparison.GTE)

    class Meta:
        db_table = "habit_schedule"
        ordering = ["valid_from"]
        constraints = [
            choices_check("frequency_type", FrequencyType, "habit_schedule_frequency_ck"),
            choices_check("target_comparison", Comparison, "habit_schedule_comparison_ck"),
            models.CheckConstraint(
                condition=~Q(frequency_type=FrequencyType.WEEKDAYS)
                | Q(weekdays_mask__gte=1, weekdays_mask__lte=127),
                name="habit_schedule_weekdays_ck",
            ),
            models.CheckConstraint(
                condition=~Q(frequency_type__in=PERIOD_FREQUENCIES) | Q(times_per_period__gte=1),
                name="habit_schedule_times_ck",
            ),
            models.CheckConstraint(
                condition=~Q(frequency_type=FrequencyType.EVERY_N_DAYS) | Q(interval_days__gte=2),
                name="habit_schedule_interval_ck",
            ),
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gte=F("valid_from")),
                name="habit_schedule_validity_ck",
            ),
            models.UniqueConstraint(
                fields=["habit"], condition=Q(valid_to__isnull=True), name="habit_schedule_one_current_uq"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.habit_id} {self.frequency_type} from {self.valid_from}"


class HabitPause(OwnedModel):
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name="pauses")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=200, default="", blank=True)

    class Meta:
        db_table = "habit_pause"
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="habit_pause_range_ck",
            )
        ]

    def __str__(self) -> str:
        return f"{self.habit_id} pause {self.start_date}"


class HabitLog(OwnedModel):
    habit = models.ForeignKey(Habit, on_delete=models.PROTECT, related_name="logs")
    log_date = models.DateField()
    timezone = models.CharField(max_length=64)
    status = models.CharField(max_length=8, choices=LogStatus.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=500, default="", blank=True)
    tracking_type_snapshot = models.CharField(max_length=8, choices=TrackingType.choices)
    target_value_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit_snapshot = models.CharField(max_length=20, default="", blank=True)
    source = models.CharField(max_length=8, choices=LogSource.choices, default=LogSource.MANUAL)
    time_entry = models.ForeignKey(
        "time_tracking.TimeEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    logged_at = models.DateTimeField(auto_now_add=True)
    is_voided = models.BooleanField(default=False)

    class Meta:
        db_table = "habit_log"
        ordering = ["log_date", "logged_at"]
        constraints = [
            choices_check("status", LogStatus, "habit_log_status_ck"),
            choices_check("source", LogSource, "habit_log_source_ck"),
            models.CheckConstraint(
                condition=~Q(status__in=[LogStatus.DONE, LogStatus.PARTIAL])
                | Q(tracking_type_snapshot=TrackingType.BOOLEAN)
                | Q(value__isnull=False),
                name="habit_log_value_required_ck",
            ),
            models.CheckConstraint(
                condition=~Q(tracking_type_snapshot=TrackingType.BOOLEAN) | Q(value__isnull=True),
                name="habit_log_boolean_no_value_ck",
            ),
            models.CheckConstraint(
                condition=Q(value__isnull=True) | Q(value__gte=0), name="habit_log_value_positive_ck"
            ),
            models.UniqueConstraint(
                fields=["habit", "log_date"],
                condition=Q(is_voided=False, tracking_type_snapshot__in=["BOOLEAN", "SCALE"]),
                name="habit_log_single_per_day_uq",
            ),
            models.UniqueConstraint(
                fields=["habit", "log_date"],
                condition=Q(is_voided=False, status__in=["SKIPPED", "REST", "MISSED"]),
                name="habit_log_single_skip_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "log_date"], name="habit_log_user_date_ix"),
            models.Index(fields=["habit", "log_date"], name="habit_log_habit_date_ix"),
        ]

    def __str__(self) -> str:
        return f"{self.habit_id} {self.log_date} {self.status}"


class HabitLogRevision(OwnedModel):
    habit_log = models.ForeignKey(HabitLog, on_delete=models.CASCADE, related_name="revisions")
    old_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "habit_log_revision"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"revision of {self.habit_log_id}"
