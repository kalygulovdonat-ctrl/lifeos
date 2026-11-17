"""HTTP layer of the schedule (SDD §7.2). No business logic here."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.schedule import selectors, services
from apps.schedule.selectors import INFO
from apps.schedule.serializers import (
    CheckConflictsSerializer,
    EventInputSerializer,
    EventPatchSerializer,
    EventViewSerializer,
    OccurrencePatchSerializer,
    RangeQuerySerializer,
    RescheduleSerializer,
    SlotSerializer,
    StatusSerializer,
)
from common.exceptions import DomainValidationError
from common.idempotency import idempotent
from common.time import local_today

FORCE = OpenApiParameter("force", bool, description="Save despite a SCHEDULE_CONFLICT (BR-013).")


def force_flag(request: Request) -> bool:
    return request.query_params.get("force") in ("1", "true", "yes")


def event_response(obj: Any, warnings: list[dict[str, Any]], code: int = 200) -> Response:
    data = dict(EventViewSerializer(services.view_for(obj)).data)
    data["warnings"] = warnings
    return Response(data, status=code)


def _input(serializer_cls: type[serializers.Serializer], request: Request, **kw: Any) -> dict[str, Any]:
    s = serializer_cls(data=request.data, context={"request": request}, **kw)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


class EventListView(APIView):
    @extend_schema(
        parameters=[RangeQuerySerializer],
        responses={200: EventViewSerializer(many=True)},
        operation_id="events_list",
    )
    def get(self, request: Request) -> Response:
        q = RangeQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        start, end = selectors.local_range(request.user, q.validated_data["from"], q.validated_data["to"])
        types = [t for t in (q.validated_data.get("time_type") or "").split(",") if t]
        items = selectors.events_in_range(
            request.user, start, end, time_types=types or None, category_id=q.validated_data.get("category")
        )
        return Response({"results": EventViewSerializer(items, many=True).data})

    @extend_schema(request=EventInputSerializer, responses={201: EventViewSerializer}, parameters=[FORCE])
    @idempotent
    def post(self, request: Request) -> Response:
        data = _input(EventInputSerializer, request)
        recurrence = data.pop("recurrence", None)
        obj, warnings = services.event_create(
            user=request.user, data=data, recurrence=recurrence, force=force_flag(request)
        )
        return event_response(obj, warnings, status.HTTP_201_CREATED)


class EventDetailView(APIView):
    @extend_schema(responses={200: EventViewSerializer})
    def get(self, request: Request, event_id: str) -> Response:
        return event_response(selectors.event_get(request.user, event_id), [])

    @extend_schema(request=EventPatchSerializer, responses={200: EventViewSerializer}, parameters=[FORCE])
    def patch(self, request: Request, event_id: str) -> Response:
        event = selectors.event_get(request.user, event_id)
        data = _input(EventPatchSerializer, request)
        data.pop("recurrence", None)
        reason = data.pop("reason", "")
        event, warnings = services.event_update(
            user=request.user, event=event, data=data, force=force_flag(request), reason=reason
        )
        return event_response(event, warnings)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, event_id: str) -> Response:
        services.event_delete(user=request.user, event=selectors.event_get(request.user, event_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventRescheduleView(APIView):
    @extend_schema(request=RescheduleSerializer, responses={200: EventViewSerializer}, parameters=[FORCE])
    def post(self, request: Request, event_id: str) -> Response:
        event = selectors.event_get(request.user, event_id)
        data = _input(RescheduleSerializer, request)
        event, warnings = services.event_reschedule(
            user=request.user, event=event, force=force_flag(request), **data
        )
        return event_response(event, warnings)


class EventStatusView(APIView):
    @extend_schema(request=StatusSerializer, responses={200: EventViewSerializer})
    def post(self, request: Request, event_id: str) -> Response:
        event = selectors.event_get(request.user, event_id)
        data = _input(StatusSerializer, request)
        return event_response(
            services.event_set_status(user=request.user, event=event, status=data["status"]), []
        )


class SeriesDetailView(APIView):
    @extend_schema(responses={200: EventViewSerializer})
    def get(self, request: Request, series_id: str) -> Response:
        return event_response(selectors.series_get(request.user, series_id), [])

    @extend_schema(request=EventPatchSerializer, responses={200: EventViewSerializer}, parameters=[FORCE])
    def patch(self, request: Request, series_id: str) -> Response:
        series = selectors.series_get(request.user, series_id)
        data = _input(EventPatchSerializer, request)
        recurrence = data.pop("recurrence", None)
        data.pop("reason", None)
        data.pop("status", None)
        series, warnings = services.series_update(
            user=request.user, series=series, data=data, recurrence=recurrence, force=force_flag(request)
        )
        return event_response(series, warnings)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, series_id: str) -> Response:
        services.series_delete(user=request.user, series=selectors.series_get(request.user, series_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


def _occurrence_start(epoch: int) -> datetime:
    try:
        return datetime.fromtimestamp(epoch, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise DomainValidationError(details={"original_start": ["Invalid occurrence."]}) from exc


class OccurrenceView(APIView):
    """`/event-series/{id}/occurrences/{epoch}/` — epoch seconds of the original start (occurrence_key)."""

    @extend_schema(
        request=OccurrencePatchSerializer, responses={200: EventViewSerializer}, parameters=[FORCE]
    )
    def patch(self, request: Request, series_id: str, epoch: int) -> Response:
        series = selectors.series_get(request.user, series_id)
        data = _input(OccurrencePatchSerializer, request)
        scope = data.pop("scope", "this")
        data.pop("reason", None)
        if scope == "this":
            data.pop("recurrence", None)
        obj, warnings = services.occurrence_edit(
            user=request.user,
            series=series,
            original_start=_occurrence_start(epoch),
            data=data,
            scope=scope,
            force=force_flag(request),
        )
        return event_response(obj, warnings)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, series_id: str, epoch: int) -> Response:
        series = selectors.series_get(request.user, series_id)
        services.occurrence_cancel(user=request.user, series=series, original_start=_occurrence_start(epoch))
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConflictsView(APIView):
    @extend_schema(parameters=[RangeQuerySerializer], responses={200: dict})
    def get(self, request: Request) -> Response:
        q = RangeQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        start, end = selectors.local_range(request.user, q.validated_data["from"], q.validated_data["to"])
        pairs = selectors.conflicts_in_range(request.user, start, end)
        return Response(
            {
                "results": [
                    {"severity": p["severity"], "a": services.brief(p["a"]), "b": services.brief(p["b"])}
                    for p in pairs
                ]
            }
        )


class CheckConflictsView(APIView):
    @extend_schema(request=CheckConflictsSerializer, responses={200: dict})
    def post(self, request: Request) -> Response:
        data = _input(CheckConflictsSerializer, request)
        overlaps = services.check_conflicts(
            user=request.user,
            start=data["start_at"],
            end=data["end_at"],
            time_type=data["time_type"],
            exclude_id=data.get("exclude_id"),
        )
        return Response(
            {
                "has_conflict": any(o.severity == selectors.CONFLICT for o in overlaps),
                "results": [
                    {"severity": o.severity, "event": services.brief(o.other)}
                    for o in overlaps
                    if o.severity != INFO
                ],
            }
        )


class FreeSlotsQuery(serializers.Serializer):
    date = serializers.DateField(required=False)
    min_minutes = serializers.IntegerField(min_value=5, max_value=720, default=15)


class FreeSlotsView(APIView):
    @extend_schema(parameters=[FreeSlotsQuery], responses={200: dict})
    def get(self, request: Request) -> Response:
        q = FreeSlotsQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        day = q.validated_data.get("date") or local_today(request.user.profile.timezone)
        ft = selectors.free_time(request.user, day, min_minutes=q.validated_data["min_minutes"])
        return Response(free_time_payload(day, ft))


def free_time_payload(day: Any, ft: selectors.FreeTime) -> dict[str, Any]:
    return {
        "date": day.isoformat(),
        "window_start": ft.window_start.isoformat(),
        "window_end": ft.window_end.isoformat(),
        "busy_minutes": ft.busy_minutes,
        "free_minutes": ft.free_minutes,
        "reserved_free_minutes": ft.reserved_free_minutes,
        "slots": SlotSerializer(
            [
                {"start_at": s, "end_at": e, "minutes": int((e - s).total_seconds() // 60)}
                for s, e in ft.slots
            ],
            many=True,
        ).data,
    }
