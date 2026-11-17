"""AI tools (SDD §9.3): read via selectors with consent checks, propose = create a draft only.

There are no write tools. Every proposal is validated by a serializer and dry-run against the
target module before it becomes an AIAction; nothing changes until the user confirms.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from rest_framework import serializers

from apps.accounts.models import User
from apps.ai_assistant.models import ActionType, AIAction, AIContextAccess, AIMessage, Scope
from apps.ai_assistant.providers.base import ToolOutcome, ToolSpec
from common.time import local_today, now

PROPOSAL_TTL = timedelta(hours=24)
MAX_ITEMS = 50

# ---------------------------------------------------------------- redaction (SDD §9.6)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_PHONE = re.compile(r"\+?\d[\d ()-]{8,}\d")


def redact(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _CARD.sub("[number]", text)
    return _PHONE.sub("[phone]", text)


def _json(data: Any) -> str:
    return redact(json.dumps(data, ensure_ascii=False, default=str))


# ---------------------------------------------------------------- tool specs

ASSUMPTIONS = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Every guess you made (missing time, date, duration…), in the user's language.",
}
DATE = {"type": "string", "description": "YYYY-MM-DD in the user's time zone"}
HHMM = {"type": "string", "description": "HH:MM, 24-hour, user's time zone"}
TIME_TYPES = ["FIXED", "FOCUS", "PERSONAL", "REST", "BUFFER", "FREE"]


def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


SPECS: list[ToolSpec] = [
    ToolSpec(
        "get_schedule",
        "Events and time blocks between two local dates (inclusive).",
        _obj({"from": DATE, "to": DATE}, ["from", "to"]),
    ),
    ToolSpec(
        "get_free_slots",
        "Free windows inside the user's working day for a local date.",
        _obj({"date": DATE}, ["date"]),
    ),
    ToolSpec(
        "get_tasks",
        "The user's tasks. status: OPEN (default), COMPLETED or ALL. Optional due range and text query.",
        _obj(
            {
                "status": {"type": "string", "enum": ["OPEN", "COMPLETED", "ALL"]},
                "due_from": DATE,
                "due_to": DATE,
                "q": {"type": "string"},
            },
            [],
        ),
    ),
    ToolSpec(
        "get_habits",
        "Habits planned for a local date with today's status and streaks.",
        _obj({"date": DATE}, []),
    ),
    ToolSpec("get_goals", "Active goals with progress.", _obj({}, [])),
    ToolSpec(
        "get_analytics",
        "Metrics for a day, week or month containing the date.",
        _obj({"period": {"type": "string", "enum": ["day", "week", "month"]}, "date": DATE}, ["period"]),
    ),
    ToolSpec(
        "get_journal_entries",
        "Journal entries the user allowed AI to read, between two dates.",
        _obj({"from": DATE, "to": DATE}, ["from", "to"]),
    ),
    ToolSpec(
        "get_wellness",
        "Mood, energy, stress and sleep averages between two dates. Observations only.",
        _obj({"from": DATE, "to": DATE}, ["from", "to"]),
    ),
    ToolSpec(
        "propose_create_task",
        "Draft a new task. The user must confirm it; nothing is created now.",
        _obj(
            {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"]},
                "due_date": DATE,
                "estimated_minutes": {"type": "integer"},
                "subtasks": {"type": "array", "items": {"type": "string"}},
                "assumptions": ASSUMPTIONS,
            },
            ["title"],
        ),
    ),
    ToolSpec(
        "propose_create_event",
        "Draft a calendar event or time block. The user must confirm it.",
        _obj(
            {
                "title": {"type": "string"},
                "date": DATE,
                "start": HHMM,
                "end": HHMM,
                "time_type": {"type": "string", "enum": TIME_TYPES},
                "task_id": {"type": "string", "description": "Optional task id from get_tasks"},
                "assumptions": ASSUMPTIONS,
            },
            ["title", "date", "start", "end"],
        ),
    ),
    ToolSpec(
        "propose_reschedule_event",
        "Draft moving an existing event (id from get_schedule) to a new time.",
        _obj(
            {
                "event_id": {"type": "string"},
                "date": DATE,
                "start": HHMM,
                "end": HHMM,
                "reason": {"type": "string"},
                "assumptions": ASSUMPTIONS,
            },
            ["event_id", "date", "start", "end"],
        ),
    ),
    ToolSpec(
        "propose_create_subtasks",
        "Draft subtasks for an existing task (id from get_tasks).",
        _obj(
            {
                "task_id": {"type": "string"},
                "titles": {"type": "array", "items": {"type": "string"}},
                "assumptions": ASSUMPTIONS,
            },
            ["task_id", "titles"],
        ),
    ),
    ToolSpec(
        "propose_log_habit",
        "Draft a habit check-off (id from get_habits).",
        _obj(
            {
                "habit_id": {"type": "string"},
                "date": DATE,
                "status": {"type": "string", "enum": ["DONE", "SKIPPED", "REST"]},
                "value": {"type": "number"},
                "assumptions": ASSUMPTIONS,
            },
            ["habit_id"],
        ),
    ),
    ToolSpec(
        "propose_journal_draft",
        "Draft a private journal entry for the user to review.",
        _obj(
            {
                "date": DATE,
                "title": {"type": "string"},
                "body": {"type": "string"},
                "assumptions": ASSUMPTIONS,
            },
            ["body"],
        ),
    ),
]

READ_SCOPES = {
    "get_schedule": Scope.SCHEDULE,
    "get_free_slots": Scope.SCHEDULE,
    "get_tasks": Scope.TASKS,
    "get_habits": Scope.HABITS,
    "get_goals": Scope.GOALS,
    "get_analytics": Scope.ANALYTICS,
    "get_journal_entries": Scope.JOURNAL,
    "get_wellness": Scope.WELLNESS,
}
PROPOSALS = {
    "propose_create_task": (ActionType.CREATE_TASK, Scope.TASKS),
    "propose_create_event": (ActionType.CREATE_EVENT, Scope.SCHEDULE),
    "propose_reschedule_event": (ActionType.RESCHEDULE_EVENT, Scope.SCHEDULE),
    "propose_create_subtasks": (ActionType.CREATE_SUBTASKS, Scope.TASKS),
    "propose_log_habit": (ActionType.LOG_HABIT, Scope.HABITS),
    "propose_journal_draft": (ActionType.CREATE_JOURNAL_DRAFT, Scope.JOURNAL),
}


# ---------------------------------------------------------------- payload schemas


class TaskPayload(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, allow_blank=True, max_length=5000, default="")
    priority = serializers.ChoiceField(choices=["LOW", "MEDIUM", "HIGH", "URGENT"], default="MEDIUM")
    due_date = serializers.DateField(required=False, allow_null=True)
    estimated_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=10_000
    )
    subtasks = serializers.ListField(
        child=serializers.CharField(max_length=300), required=False, max_length=30
    )


class EventPayload(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    date = serializers.DateField()
    start = serializers.TimeField()
    end = serializers.TimeField()
    time_type = serializers.ChoiceField(choices=TIME_TYPES, default="PERSONAL")
    task_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["end"] <= attrs["start"]:
            raise serializers.ValidationError({"end": ["Must be after start."]})
        return attrs


class ReschedulePayload(serializers.Serializer):
    event_id = serializers.UUIDField()
    date = serializers.DateField()
    start = serializers.TimeField()
    end = serializers.TimeField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300, default="")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["end"] <= attrs["start"]:
            raise serializers.ValidationError({"end": ["Must be after start."]})
        return attrs


class SubtasksPayload(serializers.Serializer):
    task_id = serializers.UUIDField()
    titles = serializers.ListField(child=serializers.CharField(max_length=300), min_length=1, max_length=30)


class HabitLogPayload(serializers.Serializer):
    habit_id = serializers.UUIDField()
    date = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=["DONE", "SKIPPED", "REST"], default="DONE")
    value = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)


class JournalPayload(serializers.Serializer):
    date = serializers.DateField(required=False)
    title = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    body = serializers.CharField(max_length=20_000)


PAYLOADS: dict[str, type[serializers.Serializer]] = {
    ActionType.CREATE_TASK: TaskPayload,
    ActionType.CREATE_EVENT: EventPayload,
    ActionType.RESCHEDULE_EVENT: ReschedulePayload,
    ActionType.CREATE_SUBTASKS: SubtasksPayload,
    ActionType.LOG_HABIT: HabitLogPayload,
    ActionType.CREATE_JOURNAL_DRAFT: JournalPayload,
}


def validate_payload(action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    s = PAYLOADS[action_type](data=payload)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


def local_dt(user: User, day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=ZoneInfo(user.profile.timezone))


# ---------------------------------------------------------------- execution context


@dataclass
class ToolContext:
    user: User
    message: AIMessage
    scopes: set[str]

    def _log(self, scope: str, object_type: str, ids: list[Any]) -> None:
        AIContextAccess.objects.create(
            user=self.user,
            message=self.message,
            scope=scope,
            object_type=object_type,
            object_ids=[str(i) for i in ids if i][:MAX_ITEMS],
        )

    def handle(self, name: str, args: dict[str, Any]) -> ToolOutcome:
        if name in READ_SCOPES:
            scope = READ_SCOPES[name]
            if scope not in self.scopes:
                return ToolOutcome(
                    f"No consent for {scope}. Tell the user they can allow it in AI settings.", True
                )
            try:
                return ToolOutcome(_json(getattr(self, name)(**args)))
            except (TypeError, ValueError, serializers.ValidationError) as exc:
                return ToolOutcome(f"Invalid arguments: {exc}", True)
        if name in PROPOSALS:
            return self.propose(name, args)
        return ToolOutcome(f"Unknown tool {name!r}. Only the listed tools exist.", True)

    # -- reads ---------------------------------------------------------------

    def _dates(self, a: str, b: str, limit: int = 62) -> tuple[date, date]:
        first, last = date.fromisoformat(a), date.fromisoformat(b)
        if last < first or (last - first).days > limit:
            raise ValueError(f"range must be 1..{limit + 1} days")
        return first, last

    def get_schedule(self, **a: Any) -> list[dict[str, Any]]:
        from apps.schedule.selectors import events_in_range, local_range

        first, last = self._dates(a["from"], a["to"])
        start, end = local_range(self.user, first, last)
        items = events_in_range(self.user, start, end, include_cancelled=False)[:MAX_ITEMS]
        self._log(Scope.SCHEDULE, "event", [e.id or e.series_id for e in items])
        tz = ZoneInfo(self.user.profile.timezone)
        return [
            {
                "id": str(e.id) if e.id else None,
                "title": e.title,
                "start": e.start_at.astimezone(tz).isoformat(),
                "end": e.end_at.astimezone(tz).isoformat(),
                "time_type": e.time_type,
                "recurring": e.series_id is not None,
            }
            for e in items
        ]

    def get_free_slots(self, **a: Any) -> dict[str, Any]:
        from apps.schedule.selectors import free_time

        ft = free_time(self.user, date.fromisoformat(a["date"]))
        tz = ZoneInfo(self.user.profile.timezone)
        self._log(Scope.SCHEDULE, "free_slots", [])
        return {
            "free_minutes": ft.free_minutes,
            "slots": [
                [s.astimezone(tz).strftime("%H:%M"), e.astimezone(tz).strftime("%H:%M")] for s, e in ft.slots
            ],
        }

    def get_tasks(self, **a: Any) -> list[dict[str, Any]]:
        from apps.tasks.models import OPEN_STATUSES
        from apps.tasks.selectors import TaskFilters, task_list

        status = a.get("status") or "OPEN"
        statuses = list(OPEN_STATUSES) if status == "OPEN" else ["COMPLETED"] if status == "COMPLETED" else []
        f = TaskFilters(
            statuses=statuses,
            q=a.get("q") or "",
            due_from=date.fromisoformat(a["due_from"]) if a.get("due_from") else None,
            due_to=date.fromisoformat(a["due_to"]) if a.get("due_to") else None,
            ordering="due_at",
        )
        items = list(task_list(self.user, f)[:MAX_ITEMS])
        self._log(Scope.TASKS, "task", [t.id for t in items])
        tz = ZoneInfo(self.user.profile.timezone)
        return [
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "due": t.due_at.astimezone(tz).date().isoformat() if t.due_at else None,
                "estimated_minutes": t.estimated_minutes,
            }
            for t in items
        ]

    def get_habits(self, **a: Any) -> list[dict[str, Any]]:
        from apps.habits.selectors import habits_for_day

        day = date.fromisoformat(a["date"]) if a.get("date") else None
        items = habits_for_day(self.user, day)
        self._log(Scope.HABITS, "habit", [i.habit.id for i in items])
        return [
            {
                "id": str(i.habit.id),
                "name": i.habit.name,
                "type": i.habit.tracking_type,
                "planned_today": i.planned,
                "status": i.status,
                "streak": i.current_streak,
            }
            for i in items
        ]

    def get_goals(self, **a: Any) -> list[dict[str, Any]]:
        from apps.goals.selectors import goal_list

        items = list(goal_list(self.user, statuses=["ACTIVE"])[:MAX_ITEMS])
        self._log(Scope.GOALS, "goal", [g.id for g in items])
        return [
            {
                "id": str(g.id),
                "title": g.title,
                "progress_pct": float(g.progress_pct),
                "target_date": g.target_date,
            }
            for g in items
        ]

    def get_analytics(self, **a: Any) -> dict[str, Any]:
        from apps.analytics.selectors import summary

        day = date.fromisoformat(a["date"]) if a.get("date") else local_today(self.user.profile.timezone)
        data = summary(self.user, a["period"], day, compare=True)
        self._log(Scope.ANALYTICS, "analytics", [])
        data.pop("wellness", None)  # wellness needs its own consent
        return data

    def get_journal_entries(self, **a: Any) -> list[dict[str, Any]]:
        from apps.journal.models import JournalEntry

        first, last = self._dates(a["from"], a["to"], 31)
        # Only entries the user explicitly marked as readable by AI (BR-076).
        items = list(
            JournalEntry.objects.filter(
                user=self.user, ai_allowed=True, entry_date__gte=first, entry_date__lte=last
            )[:20]
        )
        self._log(Scope.JOURNAL, "journal_entry", [e.id for e in items])
        return [
            {
                "date": e.entry_date.isoformat(),
                "title": e.title,
                "sections": e.sections,
                "body": e.body[:4000],
            }
            for e in items
        ]

    def get_wellness(self, **a: Any) -> dict[str, Any]:
        from apps.wellness.selectors import summary

        first, last = self._dates(a["from"], a["to"], 92)
        data = summary(self.user, first, last)
        self._log(Scope.WELLNESS, "wellness", [])
        return {k: v for k, v in data.items() if k != "series"}

    # -- proposals -------------------------------------------------------------

    def propose(self, name: str, args: dict[str, Any]) -> ToolOutcome:
        action_type, scope = PROPOSALS[name]
        if scope not in self.scopes:
            return ToolOutcome(f"No consent for {scope}; cannot draft this action.", True)
        args = dict(args)
        assumptions = [str(x)[:300] for x in (args.pop("assumptions", None) or [])][:10]
        try:
            clean = validate_payload(action_type, args)
            preview = dry_run(self.user, action_type, clean)
        except serializers.ValidationError as exc:
            # AI_INVALID_OUTPUT: nothing is created, the model is told why (SDD §9.4 step 4).
            return ToolOutcome(f"AI_INVALID_OUTPUT: {exc.detail}", True)
        action = AIAction.objects.create(
            user=self.user,
            message=self.message,
            action_type=action_type,
            payload=json.loads(json.dumps(args, default=str)),
            assumptions=assumptions,
            preview=preview,
            expires_at=now() + PROPOSAL_TTL,
        )
        return ToolOutcome(
            f"Draft {action.id} created and shown to the user for confirmation. It is NOT applied yet."
            + (f" Checks: {_json(preview)}" if preview else "")
        )


def dry_run(user: User, action_type: str, p: dict[str, Any]) -> dict[str, Any]:
    """Validates against the target module without saving (SDD §9.4 step 5)."""
    from apps.schedule.models import Event
    from apps.schedule.selectors import conflicts_for

    if action_type == ActionType.CREATE_EVENT:
        start, end = local_dt(user, p["date"], p["start"]), local_dt(user, p["date"], p["end"])
        if p.get("task_id"):
            _owned_task(user, p["task_id"])
        overlaps = [
            {"title": o.other.title, "severity": o.severity}
            for o in conflicts_for(user, start, end, p["time_type"])
            if o.severity != "INFO"
        ]
        return {"conflicts": overlaps} if overlaps else {}
    if action_type == ActionType.RESCHEDULE_EVENT:
        if not Event.objects.filter(user=user, id=p["event_id"]).exists():
            raise serializers.ValidationError(
                {"event_id": ["Unknown event (recurring occurrences cannot be moved here)."]}
            )
        start, end = local_dt(user, p["date"], p["start"]), local_dt(user, p["date"], p["end"])
        overlaps = [
            {"title": o.other.title, "severity": o.severity}
            for o in conflicts_for(user, start, end, "PERSONAL", exclude_event_id=p["event_id"])
            if o.severity != "INFO"
        ]
        return {"conflicts": overlaps} if overlaps else {}
    if action_type == ActionType.CREATE_SUBTASKS:
        _owned_task(user, p["task_id"])
    if action_type == ActionType.LOG_HABIT:
        from apps.habits.models import Habit

        if not Habit.objects.filter(user=user, id=p["habit_id"], is_archived=False).exists():
            raise serializers.ValidationError({"habit_id": ["Unknown habit."]})
    return {}


def _owned_task(user: User, task_id: Any) -> None:
    from apps.tasks.models import Task

    if not Task.objects.filter(user=user, id=task_id).exists():
        raise serializers.ValidationError({"task_id": ["Unknown task."]})
