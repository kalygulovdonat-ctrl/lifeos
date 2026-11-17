"""Wellness API (SDD §7.2)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.wellness import selectors, services
from apps.wellness.models import SleepEntry, StateCheckin
from common.fields import AwareDateTimeField
from common.idempotency import idempotent
from common.time import local_today

SCALE = {"min_value": 1, "max_value": 10, "required": False, "allow_null": True}


class CheckinSerializer(serializers.ModelSerializer):
    recorded_at = AwareDateTimeField(required=False)
    mood = serializers.IntegerField(**SCALE)
    energy = serializers.IntegerField(**SCALE)
    stress = serializers.IntegerField(**SCALE)

    class Meta:
        model = StateCheckin
        fields = ["id", "recorded_at", "local_date", "mood", "energy", "stress", "note", "source"]
        read_only_fields = ["id", "local_date", "source"]


class SleepSerializer(serializers.ModelSerializer):
    sleep_start = AwareDateTimeField()
    sleep_end = AwareDateTimeField()
    quality = serializers.IntegerField(**SCALE)
    minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = SleepEntry
        fields = ["id", "sleep_start", "sleep_end", "wake_date", "minutes", "quality", "note"]
        read_only_fields = ["id", "wake_date", "minutes"]


class RangeQuery(serializers.Serializer):
    from_ = serializers.DateField(required=False)
    to = serializers.DateField(required=False)

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        return fields


def _range(request: Request, default_days: int = 30) -> tuple[Any, Any]:
    q = RangeQuery(data=request.query_params)
    q.is_valid(raise_exception=True)
    last = q.validated_data.get("to") or local_today(request.user.profile.timezone)
    first = q.validated_data.get("from") or last - timedelta(days=default_days - 1)
    if first > last or (last - first).days > 366:
        raise serializers.ValidationError({"from": ["The range must be 1..367 days."]})
    return first, last


def _input(cls: type[serializers.Serializer], request: Request, **kw: Any) -> dict[str, Any]:
    s = cls(data=request.data, **kw)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


class CheckinListView(APIView):
    @extend_schema(
        parameters=[RangeQuery], responses={200: CheckinSerializer(many=True)}, operation_id="checkins_list"
    )
    def get(self, request: Request) -> Response:
        first, last = _range(request)
        return Response(
            {"results": CheckinSerializer(selectors.checkins(request.user, first, last), many=True).data}
        )

    @extend_schema(request=CheckinSerializer, responses={201: CheckinSerializer})
    @idempotent
    def post(self, request: Request) -> Response:
        data = _input(CheckinSerializer, request)
        item = services.checkin_create(user=request.user, **data)
        return Response(CheckinSerializer(item).data, status=status.HTTP_201_CREATED)


class CheckinDetailView(APIView):
    @extend_schema(request=CheckinSerializer, responses={200: CheckinSerializer})
    def patch(self, request: Request, checkin_id: str) -> Response:
        item = selectors.checkin_get(request.user, checkin_id)
        data = _input(CheckinSerializer, request, partial=True)
        return Response(
            CheckinSerializer(services.checkin_update(user=request.user, checkin=item, data=data)).data
        )

    @extend_schema(responses={204: None})
    def delete(self, request: Request, checkin_id: str) -> Response:
        services.checkin_delete(user=request.user, checkin=selectors.checkin_get(request.user, checkin_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class SleepListView(APIView):
    @extend_schema(
        parameters=[RangeQuery], responses={200: SleepSerializer(many=True)}, operation_id="sleep_list"
    )
    def get(self, request: Request) -> Response:
        first, last = _range(request)
        return Response(
            {"results": SleepSerializer(selectors.sleeps(request.user, first, last), many=True).data}
        )

    @extend_schema(request=SleepSerializer, responses={201: SleepSerializer})
    @idempotent
    def post(self, request: Request) -> Response:
        data = _input(SleepSerializer, request)
        item = services.sleep_create(user=request.user, **data)
        return Response(SleepSerializer(item).data, status=status.HTTP_201_CREATED)


class SleepDetailView(APIView):
    @extend_schema(request=SleepSerializer, responses={200: SleepSerializer})
    def patch(self, request: Request, sleep_id: str) -> Response:
        item = selectors.sleep_get(request.user, sleep_id)
        data = _input(SleepSerializer, request, partial=True)
        return Response(SleepSerializer(services.sleep_update(user=request.user, entry=item, data=data)).data)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, sleep_id: str) -> Response:
        services.sleep_delete(user=request.user, entry=selectors.sleep_get(request.user, sleep_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class SummaryView(APIView):
    @extend_schema(parameters=[RangeQuery], responses={200: dict})
    def get(self, request: Request) -> Response:
        first, last = _range(request)
        data = selectors.summary(request.user, first, last)
        data["signals"] = services.overload_signals(request.user)
        data["threshold_minutes"] = request.user.profile.overload_threshold_minutes
        return Response(data)
