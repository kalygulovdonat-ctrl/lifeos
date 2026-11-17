from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.models import Category
from apps.schedule.models import EventStatus, TimeType
from apps.schedule.recurrence import FREQS, WEEKDAYS, Recurrence
from apps.tasks.models import Task
from common.fields import AwareDateTimeField


class OwnedPK(serializers.PrimaryKeyRelatedField):
    """FK input limited to the requesting user's rows (SDD §6.4); a foreign id reads as unknown."""

    def __init__(self, model: type, **kwargs: Any) -> None:
        self.model = model
        kwargs.setdefault("allow_null", True)
        kwargs.setdefault("required", False)
        super().__init__(queryset=model.objects.all(), **kwargs)

    def get_queryset(self) -> Any:
        request = self.context.get("request")
        if request is None:
            return self.model.objects.none()
        return self.model.objects.filter(user=request.user)


class RecurrenceSerializer(serializers.Serializer):
    freq = serializers.ChoiceField(choices=FREQS)
    interval = serializers.IntegerField(min_value=1, max_value=366, default=1)
    by_day = serializers.ListField(child=serializers.ChoiceField(choices=WEEKDAYS), default=list)
    by_month_day = serializers.ListField(
        child=serializers.IntegerField(min_value=-31, max_value=31), default=list
    )
    count = serializers.IntegerField(min_value=1, max_value=1000, required=False, allow_null=True)
    until = serializers.DateField(required=False, allow_null=True)

    def to_internal_value(self, data: Any) -> Recurrence:  # type: ignore[override]
        return Recurrence(**super().to_internal_value(data))

    def to_representation(self, instance: Recurrence) -> dict[str, Any]:
        return {
            "freq": instance.freq,
            "interval": instance.interval,
            "by_day": instance.by_day,
            "by_month_day": instance.by_month_day,
            "count": instance.count,
            "until": instance.until.isoformat() if instance.until else None,
        }


class EventInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    location = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    start_at = AwareDateTimeField()
    end_at = AwareDateTimeField()
    all_day = serializers.BooleanField(required=False, default=False)
    timezone = serializers.CharField(max_length=64, required=False)
    time_type = serializers.ChoiceField(choices=TimeType.choices, default=TimeType.PERSONAL)
    category_id = OwnedPK(Category, source="category")
    color = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False, allow_null=True)
    task_id = OwnedPK(Task, source="task")
    reminder_minutes = serializers.IntegerField(min_value=0, max_value=10080, required=False, allow_null=True)
    recurrence = RecurrenceSerializer(required=False, allow_null=True)


class EventPatchSerializer(EventInputSerializer):
    status = serializers.ChoiceField(choices=EventStatus.choices, required=False)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["partial"] = True
        super().__init__(*args, **kwargs)
        for name in ("description", "location", "all_day", "time_type"):
            self.fields[name].default = serializers.empty


class OccurrencePatchSerializer(EventPatchSerializer):
    scope = serializers.ChoiceField(choices=["this", "following"], default="this")


class RescheduleSerializer(serializers.Serializer):
    start_at = AwareDateTimeField()
    end_at = AwareDateTimeField()
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class StatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=EventStatus.choices)


class RangeQuerySerializer(serializers.Serializer):
    from_ = serializers.DateField()
    to = serializers.DateField()
    time_type = serializers.CharField(required=False)
    category = serializers.UUIDField(required=False)

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        return fields

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["to"] < attrs["from"]:
            raise serializers.ValidationError({"to": ["Must not be before from."]})
        if (attrs["to"] - attrs["from"]).days > 92:
            raise serializers.ValidationError({"to": ["The range is limited to 93 days."]})
        return attrs


class CheckConflictsSerializer(serializers.Serializer):
    start_at = AwareDateTimeField()
    end_at = AwareDateTimeField()
    time_type = serializers.ChoiceField(choices=TimeType.choices, default=TimeType.PERSONAL)
    exclude_id = serializers.UUIDField(required=False, allow_null=True)


class EventViewSerializer(serializers.Serializer):
    """Output for both stored events and virtual occurrences (`id: null`)."""

    id = serializers.UUIDField(allow_null=True)
    series_id = serializers.UUIDField(allow_null=True)
    original_start_at = serializers.DateTimeField(allow_null=True)
    occurrence_key = serializers.CharField(allow_null=True)
    title = serializers.CharField()
    description = serializers.CharField()
    location = serializers.CharField()
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    all_day = serializers.BooleanField()
    timezone = serializers.CharField()
    time_type = serializers.CharField()
    status = serializers.CharField()
    category_id = serializers.UUIDField(allow_null=True)
    color = serializers.CharField(allow_null=True)
    task = serializers.SerializerMethodField()
    reminder_minutes = serializers.IntegerField(allow_null=True)
    recurrence = RecurrenceSerializer(allow_null=True)

    def get_task(self, obj: Any) -> dict[str, Any] | None:
        if obj.task_id is None:
            return None
        return {"id": str(obj.task_id), "title": obj.task_title}


class SlotSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    minutes = serializers.IntegerField()
