"""Goal progress formulas (SDD §5.7). Pure: takes rows, returns a percentage 0..100."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

HUNDRED = Decimal(100)


def _pct(ratio: Decimal) -> Decimal:
    ratio = max(Decimal(0), min(Decimal(1), ratio))
    return (ratio * HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def metric(start: Decimal | None, target: Decimal | None, current: Decimal | None) -> Decimal:
    """Works for decreasing goals too (e.g. 80 kg → 72 kg)."""
    if start is None or target is None or current is None or target == start:
        return Decimal(0)
    return _pct((current - start) / (target - start))


def milestones(rows: Iterable[Any]) -> Decimal:
    rows = [m for m in rows if m.status != "SKIPPED"]
    total = sum((m.weight for m in rows), Decimal(0))
    done = sum((m.weight for m in rows if m.status == "COMPLETED"), Decimal(0))
    return _pct(done / total) if total else Decimal(0)


def tasks(links: Iterable[Any]) -> Decimal:
    """links: GoalTask rows with .task loaded; cancelled and deleted tasks are excluded."""
    rows = [link for link in links if link.task.status != "CANCELLED" and link.task.deleted_at is None]
    total = sum((link.weight for link in rows), Decimal(0))
    done = sum((link.weight for link in rows if link.task.status == "COMPLETED"), Decimal(0))
    return _pct(done / total) if total else Decimal(0)


def manual(value: Decimal | None) -> Decimal:
    return _pct((value or Decimal(0)) / HUNDRED)
