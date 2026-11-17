"""Write side of the journal (SDD §4.8). Audit rows never contain entry text (SDD §6.4)."""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from apps.accounts.models import Category, Tag, User
from apps.journal.models import TEMPLATES, EntryType, JournalEntry
from common.audit import audit
from common.exceptions import ConflictError, DomainValidationError
from common.time import local_today, now

MAX_SECTION = 10_000
FIELDS = {"entry_date", "entry_type", "title", "sections", "body", "category", "is_sensitive", "ai_allowed"}


def _invalid(field: str, message: str) -> DomainValidationError:
    return DomainValidationError(details={field: [message]})


def _validate(user: User, d: dict[str, Any]) -> None:
    if d.get("entry_date") and d["entry_date"] > local_today(user.profile.timezone):
        raise _invalid("entry_date", "An entry cannot be dated in the future.")
    category: Category | None = d.get("category")
    if category is not None and category.user_id != user.id:
        raise _invalid("category_id", "Unknown category.")
    sections = d.get("sections") or {}
    if not isinstance(sections, dict):
        raise _invalid("sections", "Must be an object.")
    if d.get("entry_type") == EntryType.DAILY:
        d["template_key"] = "daily_v1"
    allowed = TEMPLATES.get(d.get("template_key") or "", ())
    unknown = [k for k in sections if k not in allowed]
    if unknown:
        raise _invalid("sections", f"Unknown section(s): {', '.join(unknown)}.")
    for key, value in sections.items():
        if not isinstance(value, str) or len(value) > MAX_SECTION:
            raise _invalid("sections", f"'{key}' must be text up to {MAX_SECTION} characters.")
    d["sections"] = {k: v for k, v in sections.items() if v.strip()}


def _set_tags(user: User, entry: JournalEntry, tags: list[Tag]) -> None:
    if any(t.user_id != user.id for t in tags):
        raise _invalid("tag_ids", "Unknown tag.")
    entry.tags.set(tags)


def _state(user: User, entry: JournalEntry, data: dict[str, Any], state: dict[str, Any]) -> None:
    if not state:
        return
    from apps.wellness.services import journal_state

    mood = state.get("mood", getattr(getattr(entry, "checkin", None), "mood", None))
    energy = state.get("energy", getattr(getattr(entry, "checkin", None), "energy", None))
    journal_state(user=user, entry=entry, mood=mood, energy=energy)


def _pop_state(data: dict[str, Any]) -> dict[str, Any]:
    return {k: data.pop(k) for k in ("mood", "energy") if k in data}


@transaction.atomic
def entry_create(*, user: User, data: dict[str, Any]) -> JournalEntry:
    state = _pop_state(data)
    tags = data.pop("tags", None)
    d = {k: v for k, v in data.items() if k in FIELDS}
    d.setdefault("entry_date", local_today(user.profile.timezone))
    _validate(user, d)
    try:
        with transaction.atomic():
            entry = JournalEntry.objects.create(user=user, **d)
    except IntegrityError as exc:
        raise ConflictError(
            "A daily reflection for this date already exists.", code="JOURNAL_DAILY_EXISTS"
        ) from exc
    if tags:
        _set_tags(user, entry, tags)
    _state(user, entry, data, state)
    audit(user=user, entity_type="journal_entry", entity_id=entry.id, action="CREATE")
    return entry


@transaction.atomic
def entry_update(*, user: User, entry: JournalEntry, data: dict[str, Any]) -> JournalEntry:
    state = _pop_state(data)
    tags = data.pop("tags", None)
    d = {k: v for k, v in data.items() if k in FIELDS and k != "entry_type"}
    merged = {
        "entry_date": entry.entry_date,
        "entry_type": entry.entry_type,
        "template_key": entry.template_key,
        "sections": entry.sections,
    } | d
    _validate(user, merged)
    d["sections"] = merged["sections"]
    for k, v in d.items():
        setattr(entry, k, v)
    try:
        with transaction.atomic():
            entry.save()
    except IntegrityError as exc:
        raise ConflictError(
            "A daily reflection for this date already exists.", code="JOURNAL_DAILY_EXISTS"
        ) from exc
    if tags is not None:
        _set_tags(user, entry, tags)
    _state(user, entry, data, state)
    audit(user=user, entity_type="journal_entry", entity_id=entry.id, action="UPDATE")
    return entry


def entry_delete(*, user: User, entry: JournalEntry) -> None:
    entry.deleted_at = now()
    entry.save(update_fields=["deleted_at", "updated_at"])
    audit(user=user, entity_type="journal_entry", entity_id=entry.id, action="DELETE")
