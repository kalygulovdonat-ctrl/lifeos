"""Shared model bases and service tables (SDD §4.1, §4.15)."""

from django.conf import settings
from django.db import models

from common.ids import uuid7


class BaseModel(models.Model):
    """UUID v7 primary key + timestamps (ADR-002)."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OwnedModel(BaseModel):
    """Every user-owned row carries user_id, including child tables (BR-001)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")

    class Meta:
        abstract = True


def choices_check(field: str, choices: type[models.TextChoices], name: str) -> models.CheckConstraint:
    """CHECK (field IN (...)) generated from TextChoices (ADR-015)."""
    return models.CheckConstraint(condition=models.Q(**{f"{field}__in": choices.values}), name=name)


class ActorType(models.TextChoices):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AI = "AI"
    ADMIN = "ADMIN"


class AuditLog(models.Model):
    """Append-only audit trail (ADR-013). Never stores passwords, tokens or journal text."""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    actor_type = models.CharField(max_length=6, choices=ActorType.choices)
    entity_type = models.CharField(max_length=40)
    entity_id = models.UUIDField()
    action = models.CharField(max_length=20)
    changes = models.JSONField(default=dict)
    request_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        indexes = [
            models.Index(fields=["user", "-created_at"], name="audit_user_created_ix"),
            models.Index(fields=["entity_type", "entity_id"], name="audit_entity_ix"),
        ]
        constraints = [choices_check("actor_type", ActorType, "audit_log_actor_type_ck")]

    def __str__(self) -> str:
        return f"{self.action} {self.entity_type}:{self.entity_id}"


class IdempotencyRecord(models.Model):
    """Stored response for an Idempotency-Key (ADR-019, NFR-012)."""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    key = models.CharField(max_length=64)
    method = models.CharField(max_length=6)
    path = models.CharField(max_length=200)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True)
    response_body = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_record"
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="idempotency_user_key_uq")]

    def __str__(self) -> str:
        return f"{self.method} {self.path} [{self.key}]"


class AliveManager(models.Manager):
    """Default manager for soft-deletable models: hides rows with deleted_at set (ADR-012)."""

    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(OwnedModel):
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = AliveManager()
    all_objects = models.Manager()  # noqa: DJ012

    class Meta:
        abstract = True
        base_manager_name = "all_objects"
