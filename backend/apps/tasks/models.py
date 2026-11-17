"""Tasks (SDD §4.5)."""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.accounts.models import Category, Tag
from common.models import ActorType, OwnedModel, SoftDeleteModel, choices_check


class TaskStatus(models.TextChoices):
    BACKLOG = "BACKLOG"
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    POSTPONED = "POSTPONED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


OPEN_STATUSES = (TaskStatus.BACKLOG, TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.POSTPONED)


class Priority(models.TextChoices):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Task(SoftDeleteModel):
    title = models.CharField(max_length=300)
    description = models.TextField(default="", blank=True)
    status = models.CharField(max_length=12, choices=TaskStatus.choices, default=TaskStatus.TODO)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.MEDIUM)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    tags = models.ManyToManyField(Tag, blank=True, db_table="task_tag", related_name="tasks")
    due_at = models.DateTimeField(null=True, blank=True)
    due_has_time = models.BooleanField(default=False)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    postponed_count = models.PositiveIntegerField(default=0)
    triaged_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)
    is_archived = models.BooleanField(default=False)

    class Meta(SoftDeleteModel.Meta):
        db_table = "task"
        ordering = ["sort_order", "-created_at"]
        constraints = [
            choices_check("status", TaskStatus, "task_status_ck"),
            choices_check("priority", Priority, "task_priority_ck"),
            models.CheckConstraint(condition=Q(title__regex=r"\S"), name="task_title_not_blank_ck"),
            models.CheckConstraint(
                condition=Q(status=TaskStatus.COMPLETED, completed_at__isnull=False)
                | (~Q(status=TaskStatus.COMPLETED) & Q(completed_at__isnull=True)),
                name="task_completed_at_ck",
            ),
            models.CheckConstraint(
                condition=Q(status=TaskStatus.CANCELLED, cancelled_at__isnull=False)
                | (~Q(status=TaskStatus.CANCELLED) & Q(cancelled_at__isnull=True)),
                name="task_cancelled_at_ck",
            ),
            models.CheckConstraint(
                condition=Q(scheduled_start__isnull=True)
                | Q(scheduled_end__isnull=True)
                | Q(scheduled_end__gt=models.F("scheduled_start")),
                name="task_scheduled_window_ck",
            ),
            models.CheckConstraint(
                condition=Q(estimated_minutes__isnull=True) | Q(estimated_minutes__gt=0),
                name="task_estimate_positive_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "status", "due_at"],
                condition=Q(deleted_at__isnull=True),
                name="task_user_status_due_ix",
            ),
            models.Index(
                fields=["user"],
                condition=Q(triaged_at__isnull=True, deleted_at__isnull=True),
                name="task_inbox_ix",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class TaskStatusChange(OwnedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="status_changes")
    from_status = models.CharField(max_length=12, null=True, blank=True)
    to_status = models.CharField(max_length=12)
    reason = models.CharField(max_length=500, default="", blank=True)
    old_due_at = models.DateTimeField(null=True, blank=True)
    new_due_at = models.DateTimeField(null=True, blank=True)
    actor_type = models.CharField(max_length=6, choices=ActorType.choices, default=ActorType.USER)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "task_status_change"
        ordering = ["changed_at"]
        constraints = [choices_check("actor_type", ActorType, "task_status_change_actor_ck")]
        indexes = [models.Index(fields=["task", "changed_at"], name="task_status_change_task_ix")]

    def __str__(self) -> str:
        return f"{self.from_status} → {self.to_status}"


class Subtask(OwnedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=300)
    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "subtask"
        ordering = ["sort_order", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_done=True, done_at__isnull=False) | Q(is_done=False, done_at__isnull=True),
                name="subtask_done_at_ck",
            )
        ]

    def __str__(self) -> str:
        return self.title
