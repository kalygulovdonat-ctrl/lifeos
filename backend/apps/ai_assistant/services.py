"""AI assistant services: consents, conversations, the request pipeline and confirmed actions.

Pipeline (SDD §9.4): the HTTP request stores the user message and a PENDING assistant message,
then a Celery task runs the orchestrator. A failing provider marks only that message as ERROR —
nothing else in LifeOS depends on AI (NFR-013).
"""

from __future__ import annotations

import logging
import time as clock
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from apps.accounts.models import User
from apps.ai_assistant.models import (
    DEFAULT_SCOPES,
    ActionStatus,
    ActionType,
    AIAction,
    AIConsent,
    AIConversation,
    AIMessage,
    MessageStatus,
    Role,
)
from apps.ai_assistant.prompts import system_blocks
from apps.ai_assistant.providers.base import AIUnavailable
from apps.ai_assistant.tools import SPECS, ToolContext, local_dt, validate_payload
from common.audit import audit
from common.exceptions import ConflictError, ForbiddenError, LifeOSError
from common.models import ActorType
from common.time import local_today, now

HISTORY_LIMIT = 20
logger = logging.getLogger("lifeos.ai")


class AIProviderUnavailable(LifeOSError):
    status_code = 503
    code = "AI_PROVIDER_UNAVAILABLE"
    message = "The AI assistant is unavailable right now. Everything else keeps working."


class AIQuotaExceeded(LifeOSError):
    status_code = 429
    code = "AI_QUOTA_EXCEEDED"
    message = "The monthly AI token limit is reached."


def get_provider() -> Any:
    if settings.AI_PROVIDER == "fake":
        from apps.ai_assistant.providers.fake import FakeProvider

        return FakeProvider()
    from apps.ai_assistant.providers.anthropic_provider import AnthropicProvider

    return AnthropicProvider()


# ---------------------------------------------------------------- consents


def active_scopes(user: User) -> set[str]:
    return set(AIConsent.objects.filter(user=user, revoked_at__isnull=True).values_list("scope", flat=True))


@transaction.atomic
def set_consents(*, user: User, scopes: list[str]) -> set[str]:
    wanted = set(scopes)
    current = active_scopes(user)
    moment = now()
    AIConsent.objects.filter(user=user, revoked_at__isnull=True, scope__in=current - wanted).update(
        revoked_at=moment
    )
    AIConsent.objects.bulk_create(AIConsent(user=user, scope=s, granted_at=moment) for s in wanted - current)
    if wanted != current:
        audit(
            user=user,
            entity_type="ai_consent",
            entity_id=user.id,
            action="UPDATE",
            changes={"scopes": [sorted(current), sorted(wanted)]},
        )
    return wanted


def enable_defaults(*, user: User) -> set[str]:
    return set_consents(user=user, scopes=sorted(active_scopes(user) | set(DEFAULT_SCOPES)))


# ---------------------------------------------------------------- conversations & messages


def tokens_this_month(user: User) -> int:
    today = local_today(user.profile.timezone)
    agg = AIMessage.objects.filter(user=user, created_at__date__gte=today.replace(day=1)).aggregate(
        i=Sum("input_tokens"), o=Sum("output_tokens")
    )
    return (agg["i"] or 0) + (agg["o"] or 0)


def conversation_create(*, user: User, title: str = "") -> AIConversation:
    return AIConversation.objects.create(
        user=user, title=title.strip()[:200], provider=settings.AI_PROVIDER, model=settings.AI_MODEL
    )


@transaction.atomic
def send_message(*, user: User, conversation: AIConversation, content: str) -> tuple[AIMessage, AIMessage]:
    if not settings.AI_ENABLED:
        raise AIProviderUnavailable()
    if not active_scopes(user):
        raise ForbiddenError("Turn the assistant on and choose what it may read.", code="AI_CONSENT_REQUIRED")
    if tokens_this_month(user) >= settings.AI_MONTHLY_TOKEN_LIMIT:
        raise AIQuotaExceeded()
    content = content.strip()
    question = AIMessage.objects.create(user=user, conversation=conversation, role=Role.USER, content=content)
    answer = AIMessage.objects.create(
        user=user, conversation=conversation, role=Role.ASSISTANT, status=MessageStatus.PENDING
    )
    if not conversation.title:
        conversation.title = content[:60]
    conversation.save(update_fields=["title", "updated_at"])

    from apps.ai_assistant.tasks import ai_generate_response

    if settings.AI_RUN_INLINE:
        transaction.on_commit(lambda: respond(answer.id))
    else:
        transaction.on_commit(lambda: ai_generate_response.delay(str(answer.id)))
    return question, answer


def respond(message_id: Any) -> AIMessage:
    """Runs the provider for one PENDING assistant message (Celery worker, queue `ai`)."""
    answer = AIMessage.objects.select_related("conversation", "user__profile").get(id=message_id)
    if answer.status != MessageStatus.PENDING:
        return answer
    user = answer.user
    history = list(
        AIMessage.objects.filter(conversation=answer.conversation, status=MessageStatus.OK)
        .exclude(id=answer.id)
        .order_by("-created_at")[:HISTORY_LIMIT]
    )[::-1]
    messages = [
        {"role": "user" if m.role == Role.USER else "assistant", "content": m.content}
        for m in history
        if m.content.strip() and m.role in (Role.USER, Role.ASSISTANT)
    ]
    while messages and messages[0]["role"] != "user":  # the API expects the first turn to be the user's
        messages.pop(0)
    ctx = ToolContext(user=user, message=answer, scopes=active_scopes(user))
    started = clock.monotonic()
    try:
        result = get_provider().run(
            system=system_blocks(user),
            messages=messages,
            tools=SPECS,
            handle_tool=ctx.handle,
            max_iterations=settings.AI_MAX_TOOL_ITERATIONS,
        )
    except AIUnavailable:
        answer.status, answer.error_code = MessageStatus.ERROR, "AI_PROVIDER_UNAVAILABLE"
    except Exception:  # an AI failure must not take the worker down; the trace goes to the logs
        logger.exception("ai_respond_failed", extra={"message_id": str(answer.id)})
        answer.status, answer.error_code = MessageStatus.ERROR, "AI_INVALID_OUTPUT"
    else:
        answer.status = MessageStatus.OK
        answer.content = result.text or ("—" if not result.notes else "")
        answer.input_tokens, answer.output_tokens = result.input_tokens, result.output_tokens
        if "refusal" in result.notes and not result.text:
            answer.status, answer.error_code = MessageStatus.ERROR, "AI_REFUSED"
    answer.latency_ms = int((clock.monotonic() - started) * 1000)
    answer.save()
    return answer


# ---------------------------------------------------------------- actions


def _not_pending() -> ConflictError:
    return ConflictError("This draft is no longer waiting for a decision.", code="AI_ACTION_NOT_PENDING")


def expire_stale(user: User | None = None) -> int:
    qs = AIAction.objects.filter(status=ActionStatus.PROPOSED, expires_at__lt=now())
    if user is not None:
        qs = qs.filter(user=user)
    return qs.update(status=ActionStatus.EXPIRED, decided_at=now())


@transaction.atomic
def action_confirm(*, user: User, action: AIAction, edited_payload: dict[str, Any] | None = None) -> AIAction:
    action = AIAction.objects.select_for_update().get(pk=action.pk, user=user)
    if action.status == ActionStatus.PROPOSED and action.expires_at < now():
        action.status = ActionStatus.EXPIRED
        action.save(update_fields=["status", "updated_at"])
        raise ConflictError("This draft has expired.", code="AI_ACTION_EXPIRED")
    if action.status != ActionStatus.PROPOSED:
        raise _not_pending()
    payload = validate_payload(action.action_type, edited_payload or action.payload)
    action.edited_payload = edited_payload
    action.status = ActionStatus.CONFIRMED
    action.decided_at = now()
    action.save()
    try:
        with transaction.atomic():
            obj_type, obj_id = execute(user, action.action_type, payload)
    except (LifeOSError, serializers.ValidationError) as exc:
        action.status = ActionStatus.FAILED
        action.error = {"code": getattr(exc, "code", "VALIDATION_ERROR"), "detail": str(exc)}
        action.save()
        return action
    action.status = ActionStatus.EXECUTED
    action.executed_at = now()
    action.result_object_type, action.result_object_id = obj_type, obj_id
    action.save()
    audit(
        user=user,
        entity_type=obj_type,
        entity_id=obj_id,
        action="AI_CREATE",
        actor_type=ActorType.AI,
        changes={"ai_action": str(action.id)},
    )
    return action


def action_reject(*, user: User, action: AIAction) -> AIAction:
    if action.status != ActionStatus.PROPOSED:
        raise _not_pending()
    action.status = ActionStatus.REJECTED
    action.decided_at = now()
    action.save(update_fields=["status", "decided_at", "updated_at"])
    return action


def execute(user: User, action_type: str, p: dict[str, Any]) -> tuple[str, Any]:
    """Runs a confirmed draft through the ordinary module services (SDD §9.4 step 8)."""
    from apps.habits.selectors import habit_get
    from apps.habits.services import habit_log_create
    from apps.journal.services import entry_create
    from apps.schedule.selectors import event_get
    from apps.schedule.services import event_create, event_reschedule
    from apps.tasks.selectors import task_get
    from apps.tasks.services import subtask_create, task_create

    if action_type == ActionType.CREATE_TASK:
        task = task_create(
            user=user,
            title=p["title"],
            description=p.get("description", ""),
            priority=p.get("priority", "MEDIUM"),
            due_date=p.get("due_date"),
            estimated_minutes=p.get("estimated_minutes"),
            subtasks=p.get("subtasks") or [],
        )
        return "task", task.id
    if action_type == ActionType.CREATE_EVENT:
        data = {
            "title": p["title"],
            "start_at": local_dt(user, p["date"], p["start"]),
            "end_at": local_dt(user, p["date"], p["end"]),
            "time_type": p["time_type"],
        }
        if p.get("task_id"):
            data["task"] = task_get(user, p["task_id"])
        event, _warnings = event_create(user=user, data=data, force=True)
        return "event", event.id
    if action_type == ActionType.RESCHEDULE_EVENT:
        event = event_get(user, p["event_id"])
        event_reschedule(
            user=user,
            event=event,
            start_at=local_dt(user, p["date"], p["start"]),
            end_at=local_dt(user, p["date"], p["end"]),
            reason=p.get("reason", ""),
            force=True,
        )
        return "event", event.id
    if action_type == ActionType.CREATE_SUBTASKS:
        task = task_get(user, p["task_id"])
        for title in p["titles"]:
            subtask_create(user=user, task=task, title=title)
        return "task", task.id
    if action_type == ActionType.LOG_HABIT:
        habit = habit_get(user, p["habit_id"])
        log = habit_log_create(
            user=user,
            habit=habit,
            log_date=p.get("date") or local_today(user.profile.timezone),
            status=p.get("status", "DONE"),
            value=p.get("value"),
            source="AI",
        )
        return "habit_log", log.id
    if action_type == ActionType.CREATE_JOURNAL_DRAFT:
        entry = entry_create(
            user=user,
            data={
                "entry_type": "FREE",
                "entry_date": p.get("date") or local_today(user.profile.timezone),
                "title": p.get("title", ""),
                "body": p["body"],
            },
        )
        return "journal_entry", entry.id
    raise ConflictError("This kind of action is not supported yet.", code="AI_ACTION_UNSUPPORTED")


REVERT_GRACE = timedelta(seconds=2)


@transaction.atomic
def action_revert(*, user: User, action: AIAction) -> AIAction:
    """BR-075: undo what a confirmed draft created, if the user has not changed it since."""
    from apps.habits.models import HabitLog
    from apps.habits.services import habit_log_void
    from apps.journal.models import JournalEntry
    from apps.journal.services import entry_delete
    from apps.schedule.models import Event
    from apps.schedule.services import event_delete
    from apps.tasks.models import Task
    from apps.tasks.services import task_delete

    def refuse() -> ConflictError:
        return ConflictError(
            "The created item was changed or this action cannot be undone.", code="AI_ACTION_NOT_REVERTIBLE"
        )

    if action.status != ActionStatus.EXECUTED or action.action_type not in (
        ActionType.CREATE_TASK,
        ActionType.CREATE_EVENT,
        ActionType.LOG_HABIT,
        ActionType.CREATE_JOURNAL_DRAFT,
    ):
        raise refuse()
    limit = action.executed_at + REVERT_GRACE
    model = {
        ActionType.CREATE_TASK: Task,
        ActionType.CREATE_EVENT: Event,
        ActionType.LOG_HABIT: HabitLog,
        ActionType.CREATE_JOURNAL_DRAFT: JournalEntry,
    }[action.action_type]
    obj = model.objects.filter(user=user, id=action.result_object_id).first()
    if obj is None or obj.updated_at > limit:
        raise refuse()
    if isinstance(obj, Task):
        task_delete(user=user, task=obj)
    elif isinstance(obj, Event):
        event_delete(user=user, event=obj)
    elif isinstance(obj, HabitLog):
        habit_log_void(user=user, log=obj)
    else:
        entry_delete(user=user, entry=obj)
    action.status = ActionStatus.REVERTED
    action.save(update_fields=["status", "updated_at"])
    audit(
        user=user,
        entity_type=action.result_object_type or "",
        entity_id=action.result_object_id,
        action="AI_REVERT",
        actor_type=ActorType.USER,
    )
    return action
