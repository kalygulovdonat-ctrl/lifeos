"""Time tracking (SDD §4.9). The active timer is a RUNNING/PAUSED entry (ADR-008)."""

from __future__ import annotations

from django.db import models
from django.db.models import F, Q

from apps.accounts.models import Category
from common.models import OwnedModel, SoftDeleteModel, choices_check


class EntryStatus(models.TextChoices):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


ACTIVE = (EntryStatus.RUNNING, EntryStatus.PAUSED)


class EntrySource(models.TextChoices):
    TIMER = "TIMER"
    MANUAL = "MANUAL"
    POMODORO = "POMODORO"
    AI = "AI"
    IMPORT = "IMPORT"


class TimeEntry(SoftDeleteModel):
    task = models.ForeignKey(
        "tasks.Task", null=True, blank=True, on_delete=models.SET_NULL, related_name="time_entries"
    )
    event = models.ForeignKey(
        "schedule.Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="time_entries"
    )
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    description = models.CharField(max_length=300, default="", blank=True)
    status = models.CharField(max_length=8, choices=EntryStatus.choices)
    source = models.CharField(max_length=8, choices=EntrySource.choices, default=EntrySource.TIMER)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    paused_seconds = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    is_focus = models.BooleanField(default=False)
    pomodoro_index = models.SmallIntegerField(null=True, blank=True)

    class Meta(SoftDeleteModel.Meta):
        db_table = "time_entry"
        ordering = ["-started_at"]
        constraints = [
            choices_check("status", EntryStatus, "time_entry_status_ck"),
            choices_check("source", EntrySource, "time_entry_source_ck"),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status__in=["RUNNING", "PAUSED"], deleted_at__isnull=True),
                name="time_entry_one_active_uq",
            ),
            models.CheckConstraint(
                condition=Q(status=EntryStatus.STOPPED, ended_at__isnull=False)
                | (~Q(status=EntryStatus.STOPPED) & Q(ended_at__isnull=True)),
                name="time_entry_stopped_ended_ck",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F("started_at")),
                name="time_entry_end_after_start_ck",
            ),
            models.CheckConstraint(
                condition=~Q(status=EntryStatus.STOPPED) | Q(duration_seconds__isnull=False),
                name="time_entry_stopped_duration_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-started_at"], name="time_entry_user_started_ix"),
            models.Index(fields=["task"], name="time_entry_task_ix"),
        ]

    def __str__(self) -> str:
        return f"{self.status} {self.started_at.isoformat()}"


class TimeEntryPause(OwnedModel):
    time_entry = models.ForeignKey(TimeEntry, on_delete=models.CASCADE, related_name="pauses")
    paused_at = models.DateTimeField()
    resumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "time_entry_pause"
        ordering = ["paused_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(resumed_at__isnull=True) | Q(resumed_at__gt=F("paused_at")),
                name="time_entry_pause_range_ck",
            ),
            models.UniqueConstraint(
                fields=["time_entry"],
                condition=Q(resumed_at__isnull=True),
                name="time_entry_one_open_pause_uq",
            ),
        ]

    def __str__(self) -> str:
        return f"pause {self.paused_at.isoformat()}"


class TimeEntryRevision(OwnedModel):
    time_entry = models.ForeignKey(TimeEntry, on_delete=models.CASCADE, related_name="revisions")
    old_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)
    reason = models.CharField(max_length=300, default="", blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "time_entry_revision"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"revision of {self.time_entry_id}"
