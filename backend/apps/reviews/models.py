"""Weekly Review (SDD §4.11)."""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from common.models import OwnedModel, choices_check


class ReviewStatus(models.TextChoices):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"


class Decision(models.TextChoices):
    CARRY_OVER = "CARRY_OVER"
    RESCHEDULE = "RESCHEDULE"
    BACKLOG = "BACKLOG"
    CANCEL = "CANCEL"
    KEEP = "KEEP"


class WeeklyReview(OwnedModel):
    week_start = models.DateField()
    week_end = models.DateField()
    timezone = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT)
    stats_snapshot = models.JSONField(default=dict)
    formula_version = models.CharField(max_length=10)
    wins = models.TextField(default="", blank=True)
    challenges = models.TextField(default="", blank=True)
    lessons = models.TextField(default="", blank=True)
    next_week_focus = models.TextField(default="", blank=True)
    week_rating = models.SmallIntegerField(null=True, blank=True)
    ai_insights = models.JSONField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "weekly_review"
        ordering = ["-week_start"]
        constraints = [
            choices_check("status", ReviewStatus, "weekly_review_status_ck"),
            models.UniqueConstraint(fields=["user", "week_start"], name="weekly_review_user_week_uq"),
            models.CheckConstraint(
                condition=Q(week_rating__isnull=True) | Q(week_rating__gte=1, week_rating__lte=10),
                name="weekly_review_rating_ck",
            ),
            models.CheckConstraint(
                condition=Q(status="COMPLETED", completed_at__isnull=False)
                | (~Q(status="COMPLETED") & Q(completed_at__isnull=True)),
                name="weekly_review_completed_at_ck",
            ),
        ]

    def __str__(self) -> str:
        return f"review {self.week_start}"


class ReviewTaskDecision(OwnedModel):
    review = models.ForeignKey(WeeklyReview, on_delete=models.CASCADE, related_name="decisions")
    task = models.ForeignKey("tasks.Task", on_delete=models.CASCADE, related_name="+")
    decision = models.CharField(max_length=12, choices=Decision.choices)
    new_due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "review_task_decision"
        constraints = [
            choices_check("decision", Decision, "review_task_decision_ck"),
            models.UniqueConstraint(fields=["review", "task"], name="review_task_decision_uq"),
        ]

    def __str__(self) -> str:
        return f"{self.task_id}: {self.decision}"
