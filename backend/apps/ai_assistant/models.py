"""AI assistant (SDD §4.14). The model only reads and proposes; people confirm (BR-070…BR-076)."""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from common.models import OwnedModel, choices_check


class Scope(models.TextChoices):
    TASKS = "TASKS"
    SCHEDULE = "SCHEDULE"
    HABITS = "HABITS"
    GOALS = "GOALS"
    JOURNAL = "JOURNAL"
    WELLNESS = "WELLNESS"
    ANALYTICS = "ANALYTICS"


# Granted together when the user turns the assistant on; JOURNAL and WELLNESS only explicitly.
DEFAULT_SCOPES = (Scope.TASKS, Scope.SCHEDULE, Scope.HABITS, Scope.GOALS, Scope.ANALYTICS)


class Role(models.TextChoices):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


class MessageStatus(models.TextChoices):
    OK = "OK"
    ERROR = "ERROR"
    PENDING = "PENDING"


class ActionType(models.TextChoices):
    CREATE_TASK = "CREATE_TASK"
    UPDATE_TASK = "UPDATE_TASK"
    CREATE_EVENT = "CREATE_EVENT"
    UPDATE_EVENT = "UPDATE_EVENT"
    RESCHEDULE_EVENT = "RESCHEDULE_EVENT"
    CREATE_SUBTASKS = "CREATE_SUBTASKS"
    LOG_HABIT = "LOG_HABIT"
    CREATE_JOURNAL_DRAFT = "CREATE_JOURNAL_DRAFT"


class ActionStatus(models.TextChoices):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    REVERTED = "REVERTED"


class AIConsent(OwnedModel):
    scope = models.CharField(max_length=12, choices=Scope.choices)
    granted_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ai_consent"
        constraints = [
            choices_check("scope", Scope, "ai_consent_scope_ck"),
            models.UniqueConstraint(
                fields=["user", "scope"], condition=Q(revoked_at__isnull=True), name="ai_consent_active_uq"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.scope}"


class AIConversation(OwnedModel):
    title = models.CharField(max_length=200, default="", blank=True)
    provider = models.CharField(max_length=30)
    model = models.CharField(max_length=60)
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = "ai_conversation"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title or str(self.id)


class AIMessage(OwnedModel):
    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=9, choices=Role.choices)
    content = models.TextField(default="", blank=True)
    status = models.CharField(max_length=8, choices=MessageStatus.choices, default=MessageStatus.OK)
    error_code = models.CharField(max_length=40, null=True, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "ai_message"
        ordering = ["created_at"]
        constraints = [
            choices_check("role", Role, "ai_message_role_ck"),
            choices_check("status", MessageStatus, "ai_message_status_ck"),
        ]

    def __str__(self) -> str:
        return f"{self.role} {self.status}"


class AIAction(OwnedModel):
    message = models.ForeignKey(AIMessage, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    payload = models.JSONField()
    payload_schema_ver = models.SmallIntegerField(default=1)
    assumptions = models.JSONField(default=list, blank=True)
    preview = models.JSONField(default=dict, blank=True)  # dry-run findings shown on the draft card
    status = models.CharField(max_length=9, choices=ActionStatus.choices, default=ActionStatus.PROPOSED)
    edited_payload = models.JSONField(null=True, blank=True)
    result_object_type = models.CharField(max_length=20, null=True, blank=True)
    result_object_id = models.UUIDField(null=True, blank=True)
    error = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ai_action"
        ordering = ["created_at"]
        constraints = [
            choices_check("action_type", ActionType, "ai_action_type_ck"),
            choices_check("status", ActionStatus, "ai_action_status_ck"),
        ]
        indexes = [models.Index(fields=["user", "status"], name="ai_action_user_status_ix")]

    def __str__(self) -> str:
        return f"{self.action_type} {self.status}"


class AIContextAccess(OwnedModel):
    message = models.ForeignKey(AIMessage, on_delete=models.CASCADE, related_name="context_access")
    scope = models.CharField(max_length=12, choices=Scope.choices)
    object_type = models.CharField(max_length=20)
    object_ids = models.JSONField(default=list)  # uuid[] in SDD; JSON keeps SQLite compatibility

    class Meta:
        db_table = "ai_context_access"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.scope}:{self.object_type}"
