"""Schedule (SDD §4.4): one-off events, recurring series expanded virtually (ADR-007)."""

from __future__ import annotations

from django.db import models
from django.db.models import F, Q

from apps.accounts.models import HEX_COLOR, Category
from common.models import OwnedModel, SoftDeleteModel, choices_check


class TimeType(models.TextChoices):
    FIXED = "FIXED"
    FOCUS = "FOCUS"
    PERSONAL = "PERSONAL"
    REST = "REST"
    BUFFER = "BUFFER"
    FREE = "FREE"


class EventStatus(models.TextChoices):
    PLANNED = "PLANNED"
    DONE = "DONE"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"


class EventFields(SoftDeleteModel):
    """Fields shared by an event and the template of a series."""

    title = models.CharField(max_length=200)
    description = models.TextField(default="", blank=True)
    location = models.CharField(max_length=200, default="", blank=True)
    color = models.CharField(max_length=7, null=True, blank=True, validators=[HEX_COLOR])
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    time_type = models.CharField(max_length=10, choices=TimeType.choices, default=TimeType.PERSONAL)
    task = models.ForeignKey("tasks.Task", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reminder_minutes = models.PositiveIntegerField(null=True, blank=True)
    timezone = models.CharField(max_length=64)
    all_day = models.BooleanField(default=False)

    class Meta(SoftDeleteModel.Meta):
        abstract = True


class EventSeries(EventFields):
    """Recurrence rule. `dtstart_at` + `timezone` give the local wall-clock start (SDD §2.3)."""

    dtstart_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    rrule = models.CharField(max_length=500)
    until_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta(EventFields.Meta):
        db_table = "event_series"
        constraints = [
            choices_check("time_type", TimeType, "event_series_time_type_ck"),
            models.CheckConstraint(condition=Q(duration_minutes__gt=0), name="event_series_duration_ck"),
        ]
        indexes = [models.Index(fields=["user", "until_at"], name="event_series_user_until_ix")]

    def __str__(self) -> str:
        return f"{self.title} [{self.rrule}]"


class EventSeriesExdate(OwnedModel):
    series = models.ForeignKey(EventSeries, on_delete=models.CASCADE, related_name="exdates")
    original_start_at = models.DateTimeField()

    class Meta:
        db_table = "event_series_exdate"
        constraints = [
            models.UniqueConstraint(fields=["series", "original_start_at"], name="event_series_exdate_uq")
        ]

    def __str__(self) -> str:
        return f"{self.series_id} minus {self.original_start_at.isoformat()}"


class Event(EventFields):
    # An override of one occurrence of a series. Overrides die with their series.
    series = models.ForeignKey(
        EventSeries, null=True, blank=True, on_delete=models.CASCADE, related_name="overrides"
    )
    original_start_at = models.DateTimeField(null=True, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=EventStatus.choices, default=EventStatus.PLANNED)

    class Meta(EventFields.Meta):
        db_table = "event"
        ordering = ["start_at"]
        constraints = [
            choices_check("time_type", TimeType, "event_time_type_ck"),
            choices_check("status", EventStatus, "event_status_ck"),
            models.CheckConstraint(condition=Q(end_at__gt=F("start_at")), name="event_end_after_start_ck"),
            models.CheckConstraint(
                condition=Q(series__isnull=True, original_start_at__isnull=True)
                | Q(series__isnull=False, original_start_at__isnull=False),
                name="event_series_original_ck",
            ),
            models.UniqueConstraint(
                fields=["series", "original_start_at"],
                condition=Q(series__isnull=False),
                name="event_series_override_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "start_at"], name="event_user_start_ix"),
            models.Index(fields=["user", "end_at"], name="event_user_end_ix"),
            models.Index(fields=["task"], name="event_task_ix"),
        ]

    def __str__(self) -> str:
        return self.title


class EventReschedule(OwnedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="reschedules")
    old_start_at = models.DateTimeField()
    old_end_at = models.DateTimeField()
    new_start_at = models.DateTimeField()
    new_end_at = models.DateTimeField()
    reason = models.CharField(max_length=300, default="", blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "event_reschedule"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"{self.event_id}: {self.old_start_at} → {self.new_start_at}"
