from datetime import timedelta

import pytest

from apps.tasks.models import Task
from common.time import now

pytestmark = pytest.mark.django_db


def test_dashboard_aggregates_day(api_client):
    api_client.post(
        "/api/v1/events/",
        {
            "title": "Пара",
            "start_at": "2026-11-18T09:00:00+06:00",
            "end_at": "2026-11-18T10:30:00+06:00",
            "time_type": "FIXED",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/events/",
        {
            "title": "Курсовая",
            "start_at": "2026-11-18T14:00:00+06:00",
            "end_at": "2026-11-18T16:00:00+06:00",
            "time_type": "FOCUS",
        },
        format="json",
    )
    today = api_client.post(
        "/api/v1/tasks/", {"title": "Сегодня", "due_date": "2026-11-18"}, format="json"
    ).json()
    late = api_client.post("/api/v1/tasks/", {"title": "Просрочено"}, format="json").json()
    Task.objects.filter(id=late["id"]).update(due_at=now() - timedelta(days=30))
    api_client.post("/api/v1/tasks/quick/", {"title": "Идея"}, format="json")

    body = api_client.get("/api/v1/dashboard/?date=2026-11-18").json()
    assert body["date"] == "2026-11-18"
    assert [e["title"] for e in body["schedule"]] == ["Пара", "Курсовая"]
    assert [t["id"] for t in body["tasks"]["today"]] == [today["id"]]
    assert late["id"] in [t["id"] for t in body["tasks"]["overdue"]]
    assert body["inbox_count"] == 1
    assert body["stats"]["planned_minutes"] == 210
    assert body["stats"]["focus_minutes"] == 120
    assert body["free_time"]["busy_minutes"] == 210
    assert body["habits"] is None


def test_dashboard_defaults_to_today_and_isolates(api_client, other_client):
    api_client.post("/api/v1/tasks/quick/", {"title": "Идея"}, format="json")
    body = other_client.get("/api/v1/dashboard/").json()
    assert body["inbox_count"] == 0
    assert body["date"]
