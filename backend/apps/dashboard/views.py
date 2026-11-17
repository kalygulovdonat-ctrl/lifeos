from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.selectors import dashboard_for_date
from apps.schedule.serializers import EventViewSerializer
from apps.schedule.views import free_time_payload
from apps.tasks.serializers import TaskSerializer
from common.time import local_today


class DashboardQuery(serializers.Serializer):
    date = serializers.DateField(required=False)


class DashboardView(APIView):
    """GET /dashboard/?date= — the whole home screen in one request (SDD §7.2)."""

    @extend_schema(parameters=[DashboardQuery], responses={200: dict})
    def get(self, request: Request) -> Response:
        q = DashboardQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        tz = request.user.profile.timezone
        day = q.validated_data.get("date") or local_today(tz)
        d = dashboard_for_date(request.user, day)
        ctx = {"request": request, "tz": tz}
        t = d.day_tasks
        return Response(
            {
                "date": day.isoformat(),
                "timezone": tz,
                "schedule": EventViewSerializer(d.events, many=True).data,
                "upcoming": EventViewSerializer(d.upcoming, many=True).data,
                "tasks": {
                    "today": TaskSerializer(t.due, many=True, context=ctx).data,
                    "overdue": TaskSerializer(t.overdue, many=True, context=ctx).data,
                    "completed_count": len(t.completed),
                    "open_count": len(t.due),
                },
                "inbox_count": d.inbox_count,
                "free_time": free_time_payload(day, d.free),
                "stats": {
                    "planned_minutes": d.planned_minutes,
                    "focus_minutes": d.focus_minutes,
                    "tasks_completed": len(t.completed),
                    "tasks_total": len(t.completed) + len(t.due),
                },
                # Phase 2 modules: present in the contract, empty until they exist.
                "habits": None,
                "goals": None,
                "active_timer": None,
            }
        )
