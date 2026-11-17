"""Write side of wellness (SDD §4.10, §5.9)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import transaction

from apps.accounts.models import User
from apps.wellness.models import CheckinSource, SleepEntry, StateCheckin
from common.audit import audit
from common.exceptions import DomainValidationError
from common.time import local_date_of, local_today, now, period_bounds

MAX_SLEEP = timedelta(hours=20)
SCALE_FIELDS = ("mood", "energy", "stress")


def _invalid(field: str, message: str) -> DomainValidationError:
    return DomainValidationError(details={field: [message]})


def _check_scale(data: dict[str, Any]) -> None:
    for key in (*SCALE_FIELDS, "quality"):
        value = data.get(key)
        if value is not None and not 1 <= value <= 10:
            raise _invalid(key, "Must be between 1 and 10.")


def checkin_create(
    *,
    user: User,
    mood: int | None = None,
    energy: int | None = None,
    stress: int | None = None,
    note: str = "",
    recorded_at: datetime | None = None,
    source: str = CheckinSource.MANUAL,
    journal_entry: Any = None,
) -> StateCheckin:
    data = {"mood": mood, "energy": energy, "stress": stress}
    _check_scale(data)
    if all(v is None for v in data.values()):
        raise _invalid("mood", "Give at least one of mood, energy or stress.")
    moment = recorded_at or now()
    if moment > now() + timedelta(minutes=5):
        raise _invalid("recorded_at", "Cannot record the future.")
    tz = user.profile.timezone
    return StateCheckin.objects.create(
        user=user,
        recorded_at=moment,
        local_date=local_date_of(moment, tz),
        timezone=tz,
        note=note.strip(),
        source=source,
        journal_entry=journal_entry,
        **data,
    )


def checkin_update(*, user: User, checkin: StateCheckin, data: dict[str, Any]) -> StateCheckin:
    merged = {k: data.get(k, getattr(checkin, k)) for k in SCALE_FIELDS}
    _check_scale(merged)
    if all(v is None for v in merged.values()):
        raise _invalid("mood", "Give at least one of mood, energy or stress.")
    for k, v in merged.items():
        setattr(checkin, k, v)
    if "note" in data:
        checkin.note = data["note"].strip()
    checkin.save()
    return checkin


def checkin_delete(*, user: User, checkin: StateCheckin) -> None:
    checkin.delete()


@transaction.atomic
def journal_state(*, user: User, entry: Any, mood: int | None, energy: int | None) -> None:
    """ADR-009: mood/energy typed in the journal live in state_checkin (source JOURNAL)."""
    existing = StateCheckin.objects.filter(user=user, journal_entry=entry).first()
    if mood is None and energy is None:
        if existing:
            existing.delete()
        return
    if existing:
        checkin_update(user=user, checkin=existing, data={"mood": mood, "energy": energy})
        return
    tz = user.profile.timezone
    moment = now()
    if entry.entry_date != local_today(tz):  # a past entry: record at noon of that day
        moment = period_bounds(tz, "day", entry.entry_date).start + timedelta(hours=12)
    checkin_create(
        user=user,
        mood=mood,
        energy=energy,
        recorded_at=moment,
        source=CheckinSource.JOURNAL,
        journal_entry=entry,
    )


def _validate_sleep(user: User, start: datetime, end: datetime, exclude: Any = None) -> None:
    if end <= start:
        raise _invalid("sleep_end", "Must be later than sleep_start.")
    if end - start > MAX_SLEEP:
        raise _invalid("sleep_end", "A sleep entry is limited to 20 hours.")
    if end > now() + timedelta(minutes=5):
        raise _invalid("sleep_end", "Cannot end in the future.")
    clash = SleepEntry.objects.filter(user=user, sleep_start__lt=end, sleep_end__gt=start)
    if exclude:
        clash = clash.exclude(id=exclude)
    if clash.exists():
        raise _invalid("sleep_start", "Overlaps another sleep entry.")


def sleep_create(
    *, user: User, sleep_start: datetime, sleep_end: datetime, quality: int | None = None, note: str = ""
) -> SleepEntry:
    _validate_sleep(user, sleep_start, sleep_end)
    _check_scale({"quality": quality})
    entry = SleepEntry.objects.create(
        user=user,
        sleep_start=sleep_start,
        sleep_end=sleep_end,
        wake_date=local_date_of(sleep_end, user.profile.timezone),
        quality=quality,
        note=note.strip(),
    )
    audit(user=user, entity_type="sleep_entry", entity_id=entry.id, action="CREATE")
    return entry


def sleep_update(*, user: User, entry: SleepEntry, data: dict[str, Any]) -> SleepEntry:
    start = data.get("sleep_start", entry.sleep_start)
    end = data.get("sleep_end", entry.sleep_end)
    _validate_sleep(user, start, end, exclude=entry.id)
    _check_scale({"quality": data.get("quality", entry.quality)})
    entry.sleep_start, entry.sleep_end = start, end
    entry.wake_date = local_date_of(end, user.profile.timezone)
    for k in ("quality", "note"):
        if k in data:
            setattr(entry, k, data[k].strip() if k == "note" else data[k])
    entry.save()
    return entry


def sleep_delete(*, user: User, entry: SleepEntry) -> None:
    entry.delete()


# ---------------------------------------------------------------- §5.9 overload


def overload_signals(user: User) -> list[dict[str, Any]]:
    """Observations for the last 7 days; never diagnoses."""
    from apps.schedule.selectors import events_in_range
    from apps.time_tracking.selectors import tracked_seconds
    from apps.wellness.selectors import summary

    profile = user.profile
    today = local_today(profile.timezone)
    first = today - timedelta(days=7)
    signals: list[dict[str, Any]] = []
    heavy = 0
    for i in range(7):
        day = first + timedelta(days=i)
        b = period_bounds(profile.timezone, "day", day)
        planned = sum(
            int((min(e.end_at, b.end) - max(e.start_at, b.start)).total_seconds() // 60)
            for e in events_in_range(user, b.start, b.end, include_cancelled=False)
            if e.time_type not in ("FREE", "REST")
        )
        actual = tracked_seconds(user, b.start, b.end) // 60
        if max(planned, actual) > profile.overload_threshold_minutes:
            heavy += 1
    if heavy >= 3:
        signals.append({"code": "HEAVY_DAYS", "days": heavy, "threshold": profile.overload_threshold_minutes})
    s = summary(user, first, today - timedelta(days=1))
    if s["sleep_entries"] >= 4 and s["sleep_minutes"] is not None and s["sleep_minutes"] < 360:
        signals.append({"code": "SHORT_SLEEP", "avg_minutes": round(s["sleep_minutes"])})
    if s["checkins"] >= 3 and s["stress"] is not None and s["stress"] >= 8:
        signals.append({"code": "HIGH_STRESS", "avg": s["stress"]})
    return signals


def overload_check(user: User) -> bool:
    """Creates at most one OVERLOAD_WARNING notification per 3 days."""
    from apps.notifications.models import Notification
    from apps.notifications.services import notification_create

    signals = overload_signals(user)
    if not signals:
        return False
    recent = Notification.objects.filter(
        user=user, type="OVERLOAD_WARNING", created_at__gte=now() - timedelta(days=3)
    ).exists()
    if recent:
        return False
    notification_create(
        user=user,
        type="OVERLOAD_WARNING",
        message_key="overload",
        params={"signals": [s["code"] for s in signals]},
        link="/wellness",
    )
    return True
