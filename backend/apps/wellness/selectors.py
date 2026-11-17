"""Read side of wellness. Every function takes the owner first."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from apps.accounts.models import User
from apps.wellness.models import SleepEntry, StateCheckin
from common.exceptions import NotFoundError


def checkins(user: User, first: date, last: date) -> QuerySet[StateCheckin]:
    return StateCheckin.objects.filter(user=user, local_date__gte=first, local_date__lte=last)


def sleeps(user: User, first: date, last: date) -> QuerySet[SleepEntry]:
    return SleepEntry.objects.filter(user=user, wake_date__gte=first, wake_date__lte=last)


def checkin_get(user: User, checkin_id: UUID | str) -> StateCheckin:
    try:
        return StateCheckin.objects.get(user=user, id=checkin_id)
    except (StateCheckin.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def sleep_get(user: User, sleep_id: UUID | str) -> SleepEntry:
    try:
        return SleepEntry.objects.get(user=user, id=sleep_id)
    except (SleepEntry.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def _avg(values: list[int]) -> float | None:
    return round(mean(values), 2) if values else None


def summary(user: User, first: date, last: date) -> dict[str, Any]:
    """Averages and a per-day series (mood/energy/stress averaged per day, sleep by wake date)."""
    c = list(checkins(user, first, last))
    s = list(sleeps(user, first, last))
    by_day: dict[date, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for item in c:
        for key in ("mood", "energy", "stress"):
            value = getattr(item, key)
            if value is not None:
                by_day[item.local_date][key].append(value)
    for item in s:
        by_day[item.wake_date]["sleep"].append(item.minutes)
        if item.quality is not None:
            by_day[item.wake_date]["quality"].append(item.quality)
    series = []
    day = first
    while day <= last:
        values = by_day.get(day, {})
        series.append(
            {
                "date": day.isoformat(),
                "mood": _avg(values.get("mood", [])),
                "energy": _avg(values.get("energy", [])),
                "stress": _avg(values.get("stress", [])),
                "sleep_minutes": sum(values.get("sleep", [])) or None,
                "sleep_quality": _avg(values.get("quality", [])),
            }
        )
        day += timedelta(days=1)
    return {
        "mood": _avg([x.mood for x in c if x.mood is not None]),
        "energy": _avg([x.energy for x in c if x.energy is not None]),
        "stress": _avg([x.stress for x in c if x.stress is not None]),
        "sleep_minutes": _avg([x.minutes for x in s]),
        "sleep_quality": _avg([x.quality for x in s if x.quality is not None]),
        "checkins": len(c),
        "sleep_entries": len(s),
        "series": series,
    }
