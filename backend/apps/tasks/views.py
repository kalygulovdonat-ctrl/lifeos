"""HTTP layer of tasks (SDD §7.2). No business logic here."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.schedule import services as schedule_services
from apps.schedule.views import FORCE, event_response, force_flag
from apps.tasks import selectors, services
from apps.tasks.models import OPEN_STATUSES, Priority, TaskStatus
from apps.tasks.serializers import (
    HistorySerializer,
    PostponeSerializer,
    QuickTaskSerializer,
    ReorderSerializer,
    ScheduleBlockSerializer,
    StatusChangeSerializer,
    SubtaskSerializer,
    TaskDetailSerializer,
    TaskPatchSerializer,
    TaskSerializer,
    TaskWriteSerializer,
)
from common.exceptions import DomainValidationError
from common.idempotency import idempotent
from common.pagination import PageNumberPagination


def _ctx(request: Request) -> dict[str, Any]:
    return {"request": request, "tz": request.user.profile.timezone}


def _input(cls: type[serializers.Serializer], request: Request) -> dict[str, Any]:
    s = cls(data=request.data, context={"request": request})
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


def _detail(request: Request, task_id: Any, code: int = 200) -> Response:
    task = selectors.task_get(request.user, task_id)
    return Response(TaskDetailSerializer(task, context=_ctx(request)).data, status=code)


class TaskListQuery(serializers.Serializer):
    status = serializers.CharField(required=False)
    priority = serializers.CharField(required=False)
    category = serializers.UUIDField(required=False)
    tag = serializers.UUIDField(required=False)
    q = serializers.CharField(required=False, max_length=200)
    due_from = serializers.DateField(required=False)
    due_to = serializers.DateField(required=False)
    inbox = serializers.BooleanField(required=False, allow_null=True, default=None)
    overdue = serializers.BooleanField(required=False, default=False)
    archived = serializers.BooleanField(required=False, default=False)
    ordering = serializers.ChoiceField(choices=list(selectors.ORDERINGS), required=False)

    def _codes(self, value: str | None, allowed: list[str], field: str) -> list[str]:
        codes = [c.strip() for c in (value or "").split(",") if c.strip()]
        if bad := [c for c in codes if c not in allowed]:
            raise serializers.ValidationError({field: [f"Unknown value(s): {', '.join(bad)}."]})
        return codes

    def to_filters(self) -> selectors.TaskFilters:
        d = self.validated_data
        statuses = d.get("status") or ""
        if statuses == "OPEN":
            status_list = list(OPEN_STATUSES)
        else:
            status_list = self._codes(statuses, TaskStatus.values, "status")
        return selectors.TaskFilters(
            statuses=status_list,
            priorities=self._codes(d.get("priority"), Priority.values, "priority"),
            category_id=d.get("category"),
            tag_id=d.get("tag"),
            q=(d.get("q") or "").strip(),
            due_from=d.get("due_from"),
            due_to=d.get("due_to"),
            inbox=d.get("inbox"),
            overdue=d.get("overdue", False),
            archived=d.get("archived", False),
            ordering=d.get("ordering") or "",
        )


class TaskListView(APIView):
    @extend_schema(
        parameters=[TaskListQuery], responses={200: TaskSerializer(many=True)}, operation_id="tasks_list"
    )
    def get(self, request: Request) -> Response:
        q = TaskListQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        qs = selectors.task_list(request.user, q.to_filters())
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(TaskSerializer(page, many=True, context=_ctx(request)).data)

    @extend_schema(request=TaskWriteSerializer, responses={201: TaskDetailSerializer})
    @idempotent
    def post(self, request: Request) -> Response:
        data = _input(TaskWriteSerializer, request)
        task = services.task_create(user=request.user, **data)
        return _detail(request, task.id, status.HTTP_201_CREATED)


class TaskQuickView(APIView):
    @extend_schema(request=QuickTaskSerializer, responses={201: TaskDetailSerializer})
    @idempotent
    def post(self, request: Request) -> Response:
        data = _input(QuickTaskSerializer, request)
        task = services.task_quick_create(user=request.user, title=data["title"])
        return _detail(request, task.id, status.HTTP_201_CREATED)


class TaskDetailView(APIView):
    @extend_schema(responses={200: TaskDetailSerializer})
    def get(self, request: Request, task_id: str) -> Response:
        return _detail(request, task_id)

    @extend_schema(request=TaskPatchSerializer, responses={200: TaskDetailSerializer})
    def patch(self, request: Request, task_id: str) -> Response:
        task = selectors.task_get(request.user, task_id)
        data = _input(TaskPatchSerializer, request)
        services.task_update(user=request.user, task=task, data=data)
        return _detail(request, task_id)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, task_id: str) -> Response:
        services.task_delete(user=request.user, task=selectors.task_get(request.user, task_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskStatusView(APIView):
    @extend_schema(request=StatusChangeSerializer, responses={200: TaskDetailSerializer})
    def post(self, request: Request, task_id: str) -> Response:
        task = selectors.task_get(request.user, task_id)
        data = _input(StatusChangeSerializer, request)
        services.task_change_status(user=request.user, task=task, **data)
        return _detail(request, task_id)


class TaskCompleteView(APIView):
    @extend_schema(request=None, responses={200: TaskDetailSerializer})
    @idempotent
    def post(self, request: Request, task_id: str) -> Response:
        services.task_complete(user=request.user, task=selectors.task_get(request.user, task_id))
        return _detail(request, task_id)


class TaskPostponeView(APIView):
    @extend_schema(request=PostponeSerializer, responses={200: TaskDetailSerializer})
    def post(self, request: Request, task_id: str) -> Response:
        task = selectors.task_get(request.user, task_id)
        data = _input(PostponeSerializer, request)
        new_due = data.get("new_due_at")
        if data.get("new_due_date"):
            if new_due:
                raise DomainValidationError(
                    details={"new_due_date": ["Send either new_due_at or new_due_date."]}
                )
            new_due = services.end_of_local_day(data["new_due_date"], request.user.profile.timezone)
        services.task_postpone(user=request.user, task=task, new_due_at=new_due, reason=data["reason"])
        return _detail(request, task_id)


class TaskTriageView(APIView):
    @extend_schema(request=None, responses={200: TaskDetailSerializer})
    def post(self, request: Request, task_id: str) -> Response:
        services.task_triage(user=request.user, task=selectors.task_get(request.user, task_id))
        return _detail(request, task_id)


class TaskArchiveView(APIView):
    archived = True

    @extend_schema(request=None, responses={200: TaskDetailSerializer})
    def post(self, request: Request, task_id: str) -> Response:
        task = selectors.task_get(request.user, task_id)
        services.task_set_archived(user=request.user, task=task, archived=self.archived)
        return _detail(request, task_id)


class TaskRestoreView(TaskArchiveView):
    archived = False


class TaskHistoryView(APIView):
    @extend_schema(responses={200: HistorySerializer(many=True)})
    def get(self, request: Request, task_id: str) -> Response:
        task = selectors.task_get(request.user, task_id)
        return Response(
            {"results": HistorySerializer(selectors.task_history(request.user, task), many=True).data}
        )


class TaskScheduleView(APIView):
    """Create a time block (event) for the task (SCH-013)."""

    @extend_schema(request=ScheduleBlockSerializer, responses={201: dict}, parameters=[FORCE])
    @idempotent
    def post(self, request: Request, task_id: str) -> Response:
        task = selectors.task_get(request.user, task_id)
        data = _input(ScheduleBlockSerializer, request)
        event, warnings = schedule_services.event_create(
            user=request.user,
            data={**data, "title": task.title, "task": task, "category": task.category},
            force=force_flag(request),
        )
        services.task_triage(user=request.user, task=task)
        return event_response(event, warnings, status.HTTP_201_CREATED)


class SubtaskListView(APIView):
    @extend_schema(responses={200: SubtaskSerializer(many=True)})
    def get(self, request: Request, task_id: str) -> Response:
        task = selectors.task_get(request.user, task_id)
        return Response(
            {"results": SubtaskSerializer(selectors.subtask_list(request.user, task), many=True).data}
        )

    @extend_schema(request=SubtaskSerializer, responses={201: SubtaskSerializer})
    def post(self, request: Request, task_id: str) -> Response:
        task = selectors.task_get(request.user, task_id)
        data = _input(SubtaskSerializer, request)
        sub = services.subtask_create(user=request.user, task=task, title=data["title"])
        return Response(SubtaskSerializer(sub).data, status=status.HTTP_201_CREATED)


class SubtaskReorderView(APIView):
    @extend_schema(request=ReorderSerializer, responses={200: SubtaskSerializer(many=True)})
    def post(self, request: Request, task_id: str) -> Response:
        task = selectors.task_get(request.user, task_id)
        data = _input(ReorderSerializer, request)
        items = services.subtask_reorder(user=request.user, task=task, ids=data["ids"])
        return Response({"results": SubtaskSerializer(items, many=True).data})


class SubtaskDetailView(APIView):
    @extend_schema(request=SubtaskSerializer, responses={200: SubtaskSerializer})
    def patch(self, request: Request, subtask_id: str) -> Response:
        sub = selectors.subtask_get(request.user, subtask_id)
        s = SubtaskSerializer(sub, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        sub = services.subtask_update(user=request.user, subtask=sub, data=dict(s.validated_data))
        return Response(SubtaskSerializer(sub).data)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, subtask_id: str) -> Response:
        services.subtask_delete(user=request.user, subtask=selectors.subtask_get(request.user, subtask_id))
        return Response(status=status.HTTP_204_NO_CONTENT)
