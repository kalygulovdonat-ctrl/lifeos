"""Audit trail helper (ADR-013)."""

from typing import Any
from uuid import UUID

from common.logging import redact
from common.models import ActorType, AuditLog
from common.request_context import current_request_id


def audit(
    *,
    user: Any,
    entity_type: str,
    entity_id: UUID,
    action: str,
    changes: dict[str, Any] | None = None,
    actor_type: str = ActorType.USER,
) -> AuditLog:
    return AuditLog.objects.create(
        user=user if getattr(user, "pk", None) else None,
        actor_type=actor_type,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changes=redact(changes or {}),
        request_id=current_request_id(),
    )


def diff(instance: Any, data: dict[str, Any]) -> dict[str, list[Any]]:
    """{field: [old, new]} for fields whose value actually changes."""
    changes: dict[str, list[Any]] = {}
    for field, new in data.items():
        old = getattr(instance, field, None)
        if old != new:
            changes[field] = [_jsonable(old), _jsonable(new)]
    return changes


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str | list | dict):
        return value
    return str(value)
