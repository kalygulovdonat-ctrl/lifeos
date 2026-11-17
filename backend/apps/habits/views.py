"""HTTP layer of habits (SDD §7.2). No business logic here."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.habits import selectors, services
from apps.habits.serializers import (
    HabitDetailSerializer,
    HabitLogInputSerializer,
    HabitLogPatchSerializer,
    HabitLogSerializer,
    HabitPauseSerializer,
    HabitSerializer,
    HabitWriteSerializer,
    StatsSerializer,
    TodaySerializer,
)
from common.idempotency import idempotent
from common.time import local_today


def _input(cls: type[serializers.Serializer], request: Request, **kw: Any) -> dict[str, Any]:
    s = cls(data=request.data, context={"request": request}, **kw)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


def _detail(request: Request, habit_id: Any, code: int = 200) -> Response:
    return Response(HabitDetailSerializer(selectors.habit_get(request.user, habit_id)).data, status=code)


class ArchivedQuery(serializers.Serializer):
    archived = serializers.BooleanField(required=False, default=False)


class HabitListView(APIView):
    @extend_schema(
        parameters=[ArchivedQuery], responses={200: HabitSerializer(many=True)}, operation_id="habits_list"
    )
    def get(self, request: Request) -> Response:
        q = ArchivedQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        items = selectors.habit_list(request.user, archived=q.validated_data["archived"])
        return Response({"results": HabitSerializer(items, many=True).data})

    @extend_schema(request=HabitWriteSerializer, responses={201: HabitDetailSerializer})
    @idempotent
    def post(self, request: Request) -> Response:
        data = _input(HabitWriteSerializer, request)
        schedule = dict(data.pop("schedule", {}) or {})
        habit = services.habit_create(user=request.user, data=data, schedule=schedule)
        return _detail(request, habit.id, status.HTTP_201_CREATED)


class HabitDetailView(APIView):
    @extend_schema(responses={200: HabitDetailSerializer})
    def get(self, request: Request, habit_id: str) -> Response:
        return _detail(request, habit_id)

    @extend_schema(request=HabitWriteSerializer, responses={200: HabitDetailSerializer})
    def patch(self, request: Request, habit_id: str) -> Response:
        habit = selectors.habit_get(request.user, habit_id)
        data = _input(HabitWriteSerializer, request, partial=True)
        schedule = data.pop("schedule", None)
        services.habit_update(
            user=request.user,
            habit=habit,
            data=data,
            schedule=dict(schedule) if schedule is not None else None,
        )
        return _detail(request, habit_id)


class HabitArchiveView(APIView):
    archived = True

    @extend_schema(request=None, responses={200: HabitDetailSerializer})
    def post(self, request: Request, habit_id: str) -> Response:
        habit = selectors.habit_get(request.user, habit_id)
        services.habit_set_archived(user=request.user, habit=habit, archived=self.archived)
        return _detail(request, habit_id)


class HabitRestoreView(HabitArchiveView):
    archived = False


class DateQuery(serializers.Serializer):
    date = serializers.DateField(required=False)


class HabitTodayView(APIView):
    @extend_schema(parameters=[DateQuery], responses={200: TodaySerializer(many=True)})
    def get(self, request: Request) -> Response:
        q = DateQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        day = q.validated_data.get("date") or local_today(request.user.profile.timezone)
        items = selectors.habits_for_day(request.user, day)
        return Response({"date": day.isoformat(), "results": TodaySerializer(items, many=True).data})


class HabitLogsView(APIView):
    @extend_schema(request=HabitLogInputSerializer, responses={201: HabitLogSerializer})
    @idempotent
    def post(self, request: Request, habit_id: str) -> Response:
        habit = selectors.habit_get(request.user, habit_id)
        data = _input(HabitLogInputSerializer, request)
        data.setdefault("log_date", local_today(request.user.profile.timezone))
        log = services.habit_log_create(user=request.user, habit=habit, **data)
        return Response(HabitLogSerializer(log).data, status=status.HTTP_201_CREATED)


class HabitLogDetailView(APIView):
    @extend_schema(request=HabitLogPatchSerializer, responses={200: HabitLogSerializer})
    def patch(self, request: Request, log_id: str) -> Response:
        log = selectors.log_get(request.user, log_id)
        data = _input(HabitLogPatchSerializer, request)
        return Response(
            HabitLogSerializer(services.habit_log_update(user=request.user, log=log, data=data)).data
        )

    @extend_schema(responses={204: None})
    def delete(self, request: Request, log_id: str) -> Response:
        services.habit_log_void(user=request.user, log=selectors.log_get(request.user, log_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class HistoryQuery(serializers.Serializer):
    from_ = serializers.DateField(required=False)
    to = serializers.DateField(required=False)

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        return fields


class HabitHistoryView(APIView):
    @extend_schema(parameters=[HistoryQuery], responses={200: dict})
    def get(self, request: Request, habit_id: str) -> Response:
        habit = selectors.habit_get(request.user, habit_id)
        q = HistoryQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        today = local_today(request.user.profile.timezone)
        last = q.validated_data.get("to") or today
        first = q.validated_data.get("from") or last - timedelta(days=29)
        if first > last or (last - first).days > 400:
            raise serializers.ValidationError({"from": ["The range must be 1..401 days."]})
        days = selectors.habit_history(request.user, habit, first, last)
        logs = [log for log in selectors.logs_between(request.user, habit, first, last)]
        return Response(
            {
                "days": [
                    {
                        **d,
                        "date": d["date"].isoformat(),
                        "value": None if d["value"] is None else str(d["value"]),
                    }
                    for d in days
                ],
                "logs": HabitLogSerializer(
                    sorted(logs, key=lambda x: x.logged_at, reverse=True), many=True
                ).data,
            }
        )


class PeriodQuery(serializers.Serializer):
    period = serializers.ChoiceField(choices=["week", "month", "year"], default="week")


class HabitStatsView(APIView):
    @extend_schema(parameters=[PeriodQuery], responses={200: StatsSerializer})
    def get(self, request: Request, habit_id: str) -> Response:
        habit = selectors.habit_get(request.user, habit_id)
        q = PeriodQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        stats = selectors.habit_stats(request.user, habit, q.validated_data["period"])
        return Response(StatsSerializer(stats).data)


class HabitPausesView(APIView):
    @extend_schema(request=HabitPauseSerializer, responses={201: HabitPauseSerializer})
    def post(self, request: Request, habit_id: str) -> Response:
        habit = selectors.habit_get(request.user, habit_id)
        data = _input(HabitPauseSerializer, request)
        pause = services.habit_pause_create(user=request.user, habit=habit, **data)
        return Response(HabitPauseSerializer(pause).data, status=status.HTTP_201_CREATED)


class HabitPauseDetailView(APIView):
    @extend_schema(responses={204: None})
    def delete(self, request: Request, pause_id: str) -> Response:
        services.habit_pause_delete(user=request.user, pause=selectors.pause_get(request.user, pause_id))
        return Response(status=status.HTTP_204_NO_CONTENT)
