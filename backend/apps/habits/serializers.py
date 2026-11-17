from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.models import Category
from apps.habits.models import (
    Comparison,
    FrequencyType,
    Habit,
    HabitLog,
    HabitPause,
    HabitSchedule,
    LogStatus,
    TrackingType,
)
from apps.schedule.serializers import OwnedPK

DECIMAL = {"max_digits": 12, "decimal_places": 2}


class ScheduleSerializer(serializers.ModelSerializer):
    frequency_type = serializers.ChoiceField(choices=FrequencyType.choices, default=FrequencyType.DAILY)
    target_value = serializers.DecimalField(**DECIMAL, required=False, allow_null=True, min_value=0)
    target_comparison = serializers.ChoiceField(choices=Comparison.choices, default=Comparison.GTE)

    class Meta:
        model = HabitSchedule
        fields = [
            "valid_from",
            "valid_to",
            "frequency_type",
            "weekdays_mask",
            "times_per_period",
            "interval_days",
            "target_value",
            "target_comparison",
        ]
        read_only_fields = ["valid_from", "valid_to"]
        extra_kwargs = {
            "weekdays_mask": {"required": False, "allow_null": True},
            "times_per_period": {"required": False, "allow_null": True},
            "interval_days": {"required": False, "allow_null": True},
        }


class HabitWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True)
    category_id = OwnedPK(Category, source="category")
    tracking_type = serializers.ChoiceField(choices=TrackingType.choices, required=False)
    unit = serializers.CharField(max_length=20, required=False, allow_blank=True)
    scale_min = serializers.IntegerField(required=False, allow_null=True, min_value=-1000, max_value=1000)
    scale_max = serializers.IntegerField(required=False, allow_null=True, min_value=-1000, max_value=1000)
    preferred_time = serializers.TimeField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False, allow_null=True)
    reminder_time = serializers.TimeField(required=False, allow_null=True)
    color = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False, allow_null=True)
    icon = serializers.CharField(max_length=40, required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(required=False)
    schedule = ScheduleSerializer(required=False)


class HabitSerializer(serializers.ModelSerializer):
    category_id = serializers.UUIDField(read_only=True, allow_null=True)
    schedule = serializers.SerializerMethodField()

    class Meta:
        model = Habit
        fields = [
            "id",
            "name",
            "description",
            "category_id",
            "tracking_type",
            "unit",
            "scale_min",
            "scale_max",
            "preferred_time",
            "start_date",
            "end_date",
            "reminder_time",
            "color",
            "icon",
            "is_active",
            "is_archived",
            "sort_order",
            "schedule",
            "created_at",
        ]
        read_only_fields = fields

    def get_schedule(self, obj: Habit) -> dict[str, Any] | None:
        from apps.habits.selectors import current_schedule

        sched = current_schedule(obj)
        return ScheduleSerializer(sched).data if sched else None


class HabitDetailSerializer(HabitSerializer):
    schedules = ScheduleSerializer(many=True, read_only=True)
    pauses = serializers.SerializerMethodField()

    class Meta(HabitSerializer.Meta):
        fields = [*HabitSerializer.Meta.fields, "schedules", "pauses"]
        read_only_fields = fields

    def get_pauses(self, obj: Habit) -> list[dict[str, Any]]:
        return HabitPauseSerializer(obj.pauses.all(), many=True).data


class HabitLogInputSerializer(serializers.Serializer):
    log_date = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=LogStatus.choices, default=LogStatus.DONE)
    value = serializers.DecimalField(**DECIMAL, required=False, allow_null=True)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class HabitLogPatchSerializer(serializers.Serializer):
    value = serializers.DecimalField(**DECIMAL, required=False, allow_null=True)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class HabitLogSerializer(serializers.ModelSerializer):
    habit_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = HabitLog
        fields = [
            "id",
            "habit_id",
            "log_date",
            "status",
            "value",
            "note",
            "tracking_type_snapshot",
            "target_value_snapshot",
            "unit_snapshot",
            "source",
            "logged_at",
            "is_voided",
        ]
        read_only_fields = fields


class HabitPauseSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitPause
        fields = ["id", "start_date", "end_date", "reason"]
        read_only_fields = ["id"]


class StatsSerializer(serializers.Serializer):
    consistency = serializers.FloatField(allow_null=True)
    success = serializers.IntegerField()
    eligible = serializers.IntegerField()
    current_streak = serializers.IntegerField()
    best_streak = serializers.IntegerField()
    total_value = serializers.DecimalField(**DECIMAL)
    done_days = serializers.IntegerField()


class TodaySerializer(serializers.Serializer):
    habit = HabitSerializer()
    planned = serializers.BooleanField()
    paused = serializers.BooleanField()
    status = serializers.CharField(allow_null=True)
    value = serializers.DecimalField(**DECIMAL, allow_null=True)
    target_value = serializers.SerializerMethodField()
    log_ids = serializers.ListField(child=serializers.UUIDField())
    period_done = serializers.IntegerField(allow_null=True)
    period_needed = serializers.IntegerField(allow_null=True)
    current_streak = serializers.IntegerField()

    def get_target_value(self, obj: Any) -> str | None:
        target = obj.schedule.target_value if obj.schedule else None
        return None if target is None else str(target)
