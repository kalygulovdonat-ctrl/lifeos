"""Goals (SDD §4.7): optional hierarchy, milestones, M:N with tasks (ADR-005)."""

from __future__ import annotations

from django.db import models
from django.db.models import F, Q

from apps.accounts.models import Category
from common.models import OwnedModel, SoftDeleteModel, choices_check


class GoalLevel(models.TextChoices):
    VISION = "VISION"
    YEARLY = "YEARLY"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"
    CUSTOM = "CUSTOM"


class GoalStatus(models.TextChoices):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class ProgressType(models.TextChoices):
    METRIC = "METRIC"
    MILESTONES = "MILESTONES"
    TASKS = "TASKS"
    MANUAL = "MANUAL"


class MilestoneStatus(models.TextChoices):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"


class ProgressSource(models.TextChoices):
    MANUAL = "MANUAL"
    TASK = "TASK"
    MILESTONE = "MILESTONE"
    HABIT = "HABIT"
    RECALC = "RECALC"


class Goal(SoftDeleteModel):
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    level = models.CharField(max_length=10, choices=GoalLevel.choices, default=GoalLevel.CUSTOM)
    title = models.CharField(max_length=200)
    description = models.TextField(default="", blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=10, choices=GoalStatus.choices, default=GoalStatus.ACTIVE)
    start_date = models.DateField()
    target_date = models.DateField(null=True, blank=True)
    progress_type = models.CharField(
        max_length=10, choices=ProgressType.choices, default=ProgressType.MILESTONES
    )
    metric_unit = models.CharField(max_length=20, default="", blank=True)
    start_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    progress_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    tasks = models.ManyToManyField("tasks.Task", through="GoalTask", related_name="goals", blank=True)

    class Meta(SoftDeleteModel.Meta):
        db_table = "goal"
        ordering = ["target_date", "created_at"]
        constraints = [
            choices_check("level", GoalLevel, "goal_level_ck"),
            choices_check("status", GoalStatus, "goal_status_ck"),
            choices_check("progress_type", ProgressType, "goal_progress_type_ck"),
            models.CheckConstraint(
                condition=Q(target_date__isnull=True) | Q(target_date__gte=F("start_date")),
                name="goal_target_after_start_ck",
            ),
            models.CheckConstraint(
                condition=~Q(progress_type=ProgressType.METRIC)
                | (
                    Q(start_value__isnull=False, target_value__isnull=False)
                    & ~Q(target_value=F("start_value"))
                ),
                name="goal_metric_values_ck",
            ),
            models.CheckConstraint(
                condition=Q(progress_pct__gte=0, progress_pct__lte=100), name="goal_progress_range_ck"
            ),
            models.CheckConstraint(
                condition=Q(status=GoalStatus.COMPLETED, completed_at__isnull=False)
                | (~Q(status=GoalStatus.COMPLETED) & Q(completed_at__isnull=True)),
                name="goal_completed_at_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="goal_user_status_ix"),
            models.Index(fields=["parent"], name="goal_parent_ix"),
        ]

    def __str__(self) -> str:
        return self.title


class Milestone(OwnedModel):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=200)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=MilestoneStatus.choices, default=MilestoneStatus.PENDING)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    completed_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "milestone"
        ordering = ["sort_order", "due_date", "created_at"]
        constraints = [
            choices_check("status", MilestoneStatus, "milestone_status_ck"),
            models.CheckConstraint(condition=Q(weight__gt=0), name="milestone_weight_ck"),
        ]

    def __str__(self) -> str:
        return self.title


class GoalTask(OwnedModel):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="task_links")
    task = models.ForeignKey("tasks.Task", on_delete=models.CASCADE, related_name="goal_links")
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1)

    class Meta:
        db_table = "goal_task"
        constraints = [
            models.UniqueConstraint(fields=["goal", "task"], name="goal_task_uq"),
            models.CheckConstraint(condition=Q(weight__gt=0), name="goal_task_weight_ck"),
        ]

    def __str__(self) -> str:
        return f"{self.goal_id} ↔ {self.task_id}"


class GoalProgress(OwnedModel):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="progress_history")
    recorded_at = models.DateTimeField(auto_now_add=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    progress_pct = models.DecimalField(max_digits=5, decimal_places=2)
    source = models.CharField(max_length=10, choices=ProgressSource.choices)
    source_id = models.UUIDField(null=True, blank=True)
    note = models.CharField(max_length=300, default="", blank=True)

    class Meta:
        db_table = "goal_progress"
        ordering = ["recorded_at"]
        constraints = [choices_check("source", ProgressSource, "goal_progress_source_ck")]

    def __str__(self) -> str:
        return f"{self.goal_id} {self.progress_pct}%"


class GoalStatusChange(OwnedModel):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="status_changes")
    from_status = models.CharField(max_length=10, null=True, blank=True)
    to_status = models.CharField(max_length=10)
    reason = models.CharField(max_length=300, default="", blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "goal_status_change"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"{self.from_status} → {self.to_status}"
