"""Serializer fields shared by modules (SDD §2.6)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone as dj_timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers


class AwareDateTimeField(serializers.DateTimeField):
    """ISO 8601 datetime that must carry an explicit UTC offset; naive input is a 400."""

    default_error_messages = {"naive": "Datetime must include a UTC offset, e.g. 2026-11-18T10:00:00+06:00."}

    def to_internal_value(self, value: Any) -> datetime:
        if isinstance(value, str):
            try:
                parsed = parse_datetime(value.strip())
            except ValueError:
                parsed = None
            if parsed is not None and dj_timezone.is_naive(parsed):
                self.fail("naive")
        return super().to_internal_value(value)


class CommaListField(serializers.CharField):
    """`?status=TODO,IN_PROGRESS` → ["TODO", "IN_PROGRESS"]."""

    def to_internal_value(self, data: Any) -> list[str]:  # type: ignore[override]
        raw = super().to_internal_value(data)
        return [part.strip() for part in raw.split(",") if part.strip()]
