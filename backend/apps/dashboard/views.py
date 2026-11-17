from __future__ import annotations

from datetime import date
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.selectors import dashboard_for_date
from apps.goals import selectors as goal_selectors
from apps.goals.views import GoalSerializer
from apps.habits import selectors as habit_selectors
from apps.habits.serializers import TodaySerializer
from apps.schedule.serializers import EventViewSerializer
from apps.schedule.views import free_time_payload
from apps.tasks.serializers import TaskSerializer
from apps.time_tracking import selectors as time_selectors
from apps.time_tracking.views import TimeEntrySerializer
from common.time import local_today, period_bounds

GOALS_LIMIT = 4


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
                "habits": _habits(request, day),
                "goals": _goals(request),
                "active_timer": _timer(request),
                "tracked_minutes": _tracked_minutes(request, day),
            }
        )


def _habits(request: Request, day: date) -> dict[str, Any]:
    items = [i for i in habit_selectors.habits_for_day(request.user, day) if i.planned and not i.paused]
    return {
        "planned": len(items),
        "done": sum(1 for i in items if i.status == "DONE"),
        "items": TodaySerializer(items, many=True).data,
    }


def _goals(request: Request) -> list[dict[str, Any]]:
    goals = goal_selectors.goal_list(request.user, statuses=["ACTIVE"]).order_by(
        "target_date", "-progress_pct"
    )
    return GoalSerializer(goals[:GOALS_LIMIT], many=True).data


def _timer(request: Request) -> dict[str, Any] | None:
    entry = time_selectors.active_timer(request.user)
    return TimeEntrySerializer(entry).data if entry else None


def _tracked_minutes(request: Request, day: date) -> int:
    bounds = period_bounds(request.user.profile.timezone, "day", day)
    return time_selectors.tracked_seconds(request.user, bounds.start, bounds.end) // 60
