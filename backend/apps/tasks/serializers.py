from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.models import Category, Tag
from apps.schedule.models import TimeType
from apps.schedule.serializers import OwnedPK
from apps.tasks.models import Priority, Subtask, Task, TaskStatus, TaskStatusChange
from common.fields import AwareDateTimeField
from common.time import local_date_of


class TaskWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=TaskStatus.choices, required=False)
    priority = serializers.ChoiceField(choices=Priority.choices, required=False)
    category_id = OwnedPK(Category, source="category")
    tag_ids = OwnedPK(Tag, source="tags", many=True, allow_null=False, required=False)
    due_at = AwareDateTimeField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    scheduled_start = AwareDateTimeField(required=False, allow_null=True)
    scheduled_end = AwareDateTimeField(required=False, allow_null=True)
    estimated_minutes = serializers.IntegerField(
        min_value=1, max_value=100_000, required=False, allow_null=True
    )
    sort_order = serializers.IntegerField(required=False)
    subtasks = serializers.ListField(
        child=serializers.CharField(max_length=300), required=False, max_length=100
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if "due_at" in attrs and "due_date" in attrs:
            raise serializers.ValidationError({"due_date": ["Send either due_at or due_date."]})
        return attrs


class TaskPatchSerializer(TaskWriteSerializer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["partial"] = True
        super().__init__(*args, **kwargs)
        self.fields.pop("status")
        self.fields.pop("subtasks")


class QuickTaskSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300)


class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtask
        fields = ["id", "title", "is_done", "done_at", "sort_order"]
        read_only_fields = ["id", "done_at"]


class TaskSerializer(serializers.ModelSerializer):
    category_id = serializers.UUIDField(read_only=True, allow_null=True)
    tag_ids = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    in_inbox = serializers.SerializerMethodField()
    subtasks_total = serializers.IntegerField(read_only=True, default=0)
    subtasks_done = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "category_id",
            "tag_ids",
            "due_at",
            "due_has_time",
            "due_date",
            "scheduled_start",
            "scheduled_end",
            "estimated_minutes",
            "completed_at",
            "cancelled_at",
            "postponed_count",
            "triaged_at",
            "in_inbox",
            "is_overdue",
            "sort_order",
            "is_archived",
            "subtasks_total",
            "subtasks_done",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_tag_ids(self, obj: Task) -> list[str]:
        return [str(t.id) for t in obj.tags.all()]

    def get_due_date(self, obj: Task) -> str | None:
        if obj.due_at is None:
            return None
        tz = self.context.get("tz") or "UTC"
        return local_date_of(obj.due_at, tz).isoformat()

    def get_is_overdue(self, obj: Task) -> bool:
        from apps.tasks.selectors import is_overdue

        return is_overdue(obj)

    def get_in_inbox(self, obj: Task) -> bool:
        return obj.triaged_at is None


class TaskDetailSerializer(TaskSerializer):
    subtasks = SubtaskSerializer(many=True, read_only=True)

    class Meta(TaskSerializer.Meta):
        fields = [*TaskSerializer.Meta.fields, "subtasks"]
        read_only_fields = fields


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TaskStatus.choices)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    new_due_at = AwareDateTimeField(required=False, allow_null=True)


class PostponeSerializer(serializers.Serializer):
    new_due_at = AwareDateTimeField(required=False, allow_null=True)
    new_due_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class HistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskStatusChange
        fields = [
            "id",
            "from_status",
            "to_status",
            "reason",
            "old_due_at",
            "new_due_at",
            "actor_type",
            "changed_at",
        ]


class ScheduleBlockSerializer(serializers.Serializer):
    start_at = AwareDateTimeField()
    end_at = AwareDateTimeField()
    time_type = serializers.ChoiceField(choices=TimeType.choices, default=TimeType.FOCUS)


class ReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), max_length=100)
