"""HTTP layer of time tracking (SDD §7.2)."""

from __future__ import annotations

from typing import Any

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Category
from apps.schedule.models import Event
from apps.schedule.selectors import local_range
from apps.schedule.serializers import OwnedPK
from apps.tasks.models import Task
from apps.time_tracking import selectors, services
from apps.time_tracking.models import TimeEntry
from common.fields import AwareDateTimeField
from common.idempotency import idempotent
from common.pagination import PageNumberPagination


class TimeEntrySerializer(serializers.ModelSerializer):
    task = serializers.SerializerMethodField()
    task_id = serializers.UUIDField(read_only=True, allow_null=True)
    event_id = serializers.UUIDField(read_only=True, allow_null=True)
    category_id = serializers.UUIDField(read_only=True, allow_null=True)
    elapsed_seconds = serializers.SerializerMethodField()
    open_pause_at = serializers.SerializerMethodField()

    class Meta:
        model = TimeEntry
        fields = [
            "id",
            "task",
            "task_id",
            "event_id",
            "category_id",
            "description",
            "status",
            "source",
            "started_at",
            "ended_at",
            "paused_seconds",
            "duration_seconds",
            "elapsed_seconds",
            "open_pause_at",
            "is_focus",
        ]
        read_only_fields = fields

    def get_task(self, obj: TimeEntry) -> dict[str, Any] | None:
        if obj.task_id is None or obj.task is None:
            return None
        return {"id": str(obj.task_id), "title": obj.task.title}

    def get_elapsed_seconds(self, obj: TimeEntry) -> int:
        return selectors.elapsed_seconds(obj)

    def get_open_pause_at(self, obj: TimeEntry) -> str | None:
        if obj.status != "PAUSED":
            return None
        pause = next((p for p in obj.pauses.all() if p.resumed_at is None), None)
        return pause.paused_at.isoformat() if pause else None


class LinksSerializer(serializers.Serializer):
    task_id = OwnedPK(Task, source="task")
    event_id = OwnedPK(Event, source="event")
    category_id = OwnedPK(Category, source="category")
    description = serializers.CharField(max_length=300, required=False, allow_blank=True)
    is_focus = serializers.BooleanField(required=False)


class ManualEntrySerializer(LinksSerializer):
    started_at = AwareDateTimeField()
    ended_at = AwareDateTimeField()


class EntryPatchSerializer(LinksSerializer):
    started_at = AwareDateTimeField(required=False)
    ended_at = AwareDateTimeField(required=False)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


def _input(cls: type[serializers.Serializer], request: Request) -> dict[str, Any]:
    s = cls(data=request.data, context={"request": request})
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


def _entry(
    entry: TimeEntry | None, warnings: list[dict[str, Any]] | None = None, code: int = 200
) -> Response:
    if entry is None:  # an explicit JSON null: "no active timer"
        return HttpResponse(b"null", content_type="application/json", status=code)
    entry = TimeEntry.all_objects.select_related("task").prefetch_related("pauses").get(pk=entry.pk)
    data = dict(TimeEntrySerializer(entry).data)
    if warnings is not None:
        data["warnings"] = warnings
    return Response(data, status=code)


class TimerView(APIView):
    @extend_schema(responses={200: TimeEntrySerializer})
    def get(self, request: Request) -> Response:
        return _entry(selectors.active_timer(request.user))


class TimerStartView(APIView):
    @extend_schema(request=LinksSerializer, responses={201: TimeEntrySerializer})
    @idempotent
    def post(self, request: Request) -> Response:
        entry = services.timer_start(user=request.user, data=_input(LinksSerializer, request))
        return _entry(entry, code=status.HTTP_201_CREATED)


class TimerPauseView(APIView):
    @extend_schema(request=None, responses={200: TimeEntrySerializer})
    def post(self, request: Request) -> Response:
        return _entry(services.timer_pause(user=request.user))


class TimerResumeView(APIView):
    @extend_schema(request=None, responses={200: TimeEntrySerializer})
    def post(self, request: Request) -> Response:
        return _entry(services.timer_resume(user=request.user))


class TimerStopView(APIView):
    @extend_schema(request=None, responses={200: TimeEntrySerializer})
    def post(self, request: Request) -> Response:
        entry, warnings = services.timer_stop(user=request.user)
        return _entry(entry, warnings)


class TimerDiscardView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        services.timer_discard(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RangeQuery(serializers.Serializer):
    from_ = serializers.DateField()
    to = serializers.DateField()
    task = serializers.UUIDField(required=False)
    category = serializers.UUIDField(required=False)

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        return fields

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["to"] < attrs["from"] or (attrs["to"] - attrs["from"]).days > 92:
            raise serializers.ValidationError({"to": ["The range must be 1..93 days."]})
        return attrs


class TimeEntryListView(APIView):
    @extend_schema(
        parameters=[RangeQuery],
        responses={200: TimeEntrySerializer(many=True)},
        operation_id="time_entries_list",
    )
    def get(self, request: Request) -> Response:
        q = RangeQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        d = q.validated_data
        start, end = local_range(request.user, d["from"], d["to"])
        qs = selectors.entries_in_range(
            request.user, start, end, task_id=d.get("task"), category_id=d.get("category")
        ).prefetch_related("pauses")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        response = paginator.get_paginated_response(TimeEntrySerializer(page, many=True).data)
        response.data["total_seconds"] = selectors.tracked_seconds(request.user, start, end)
        return response

    @extend_schema(request=ManualEntrySerializer, responses={201: TimeEntrySerializer})
    @idempotent
    def post(self, request: Request) -> Response:
        data = _input(ManualEntrySerializer, request)
        start, end = data.pop("started_at"), data.pop("ended_at")
        entry, warnings = services.entry_create_manual(
            user=request.user, started_at=start, ended_at=end, data=data
        )
        return _entry(entry, warnings, status.HTTP_201_CREATED)


class TimeEntryDetailView(APIView):
    @extend_schema(request=EntryPatchSerializer, responses={200: TimeEntrySerializer})
    def patch(self, request: Request, entry_id: str) -> Response:
        entry = selectors.entry_get(request.user, entry_id)
        data = _input(EntryPatchSerializer, request)
        reason = data.pop("reason", "")
        entry, warnings = services.entry_update(user=request.user, entry=entry, data=data, reason=reason)
        return _entry(entry, warnings)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, entry_id: str) -> Response:
        services.entry_delete(user=request.user, entry=selectors.entry_get(request.user, entry_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlanVsActualView(APIView):
    @extend_schema(parameters=[RangeQuery], responses={200: dict})
    def get(self, request: Request) -> Response:
        q = RangeQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        start, end = local_range(request.user, q.validated_data["from"], q.validated_data["to"])
        r = selectors.plan_vs_actual(request.user, start, end)
        return Response(
            {
                "planned_minutes": r.planned_minutes,
                "matched_minutes": r.matched_minutes,
                "actual_minutes": r.actual_minutes,
                "unplanned_minutes": r.unplanned_minutes,
                "accuracy": r.accuracy,
                "focus_minutes": selectors.tracked_seconds(request.user, start, end, focus_only=True) // 60,
                "items": [
                    {
                        "title": i["event"].title,
                        "start_at": i["event"].start_at.isoformat(),
                        "time_type": i["event"].time_type,
                        "planned_minutes": i["planned_seconds"] // 60,
                        "actual_minutes": i["actual_seconds"] // 60,
                    }
                    for i in r.items
                ],
            }
        )
