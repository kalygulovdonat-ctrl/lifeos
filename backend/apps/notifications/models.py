"""In-app notifications and reminders (SDD §4.13, ADR-020)."""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from common.models import OwnedModel, choices_check


class TargetType(models.TextChoices):
    EVENT = "EVENT"
    TASK = "TASK"
    HABIT = "HABIT"
    REVIEW = "REVIEW"


class ReminderStatus(models.TextChoices):
    PENDING = "PENDING"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


class Reminder(OwnedModel):
    target_type = models.CharField(max_length=12, choices=TargetType.choices)
    target_id = models.UUIDField()
    remind_at = models.DateTimeField()
    status = models.CharField(max_length=9, choices=ReminderStatus.choices, default=ReminderStatus.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reminder"
        constraints = [
            choices_check("target_type", TargetType, "reminder_target_type_ck"),
            choices_check("status", ReminderStatus, "reminder_status_ck"),
            models.UniqueConstraint(
                fields=["target_type", "target_id", "remind_at"], name="reminder_target_uq"
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "remind_at"], condition=Q(status="PENDING"), name="reminder_pending_ix"
            )
        ]

    def __str__(self) -> str:
        return f"{self.target_type}:{self.target_id} @ {self.remind_at}"


class Notification(OwnedModel):
    type = models.CharField(max_length=30)
    message_key = models.CharField(max_length=80)
    params = models.JSONField(default=dict, blank=True)
    link = models.CharField(max_length=200, default="", blank=True)
    reminder = models.ForeignKey(Reminder, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at", "-created_at"], name="notification_user_read_ix")]

    def __str__(self) -> str:
        return f"{self.type} → {self.user_id}"
