"""Analytics API (SDD §7.2): one summary per day / week / month."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.selectors import summary
from common.time import local_today


class SummaryQuery(serializers.Serializer):
    date = serializers.DateField(required=False)
    compare = serializers.BooleanField(required=False, default=True)


class AnalyticsView(APIView):
    period: str = "week"

    @extend_schema(parameters=[SummaryQuery], responses={200: dict})
    def get(self, request: Request) -> Response:
        q = SummaryQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        anchor = q.validated_data.get("date") or local_today(request.user.profile.timezone)
        return Response(summary(request.user, self.period, anchor, compare=q.validated_data["compare"]))  # type: ignore[arg-type]


class DailyView(AnalyticsView):
    period = "day"


class WeeklyView(AnalyticsView):
    period = "week"


class MonthlyView(AnalyticsView):
    period = "month"
