from datetime import timedelta

import pytest

from apps.analytics.selectors import metric
from apps.tasks.models import Task
from common.time import now

pytestmark = pytest.mark.django_db


def test_empty_week_is_valid_report(api_client):
    body = api_client.get("/api/v1/analytics/weekly/").json()
    assert body["tasks"]["completion_rate"] == {
        "key": "task_completion_rate",
        "value": None,
        "numerator": 0,
        "denominator": 0,
        "reason": "NO_DATA",
    }
    assert body["habits"]["consistency"]["reason"] == "NO_DATA"
    assert len(body["series"]) == 7
    assert body["formula_version"] == "2026.1"


def test_task_completion_rate_rules(api_client, user):
    for title in ("a", "b", "c"):
        t = api_client.post("/api/v1/tasks/", {"title": title}, format="json").json()
        if title != "c":
            api_client.post(f"/api/v1/tasks/{t['id']}/complete/")
        else:
            Task.objects.filter(id=t["id"]).update(due_at=now() - timedelta(minutes=5))
    cancelled = api_client.post("/api/v1/tasks/", {"title": "x"}, format="json").json()
    Task.objects.filter(id=cancelled["id"]).update(due_at=now() - timedelta(minutes=5))
    api_client.post(f"/api/v1/tasks/{cancelled['id']}/status/", {"status": "CANCELLED"}, format="json")
    future = api_client.post("/api/v1/tasks/", {"title": "f", "due_date": "2099-01-01"}, format="json")
    assert future.status_code == 201
    body = api_client.get("/api/v1/analytics/daily/").json()
    rate = body["tasks"]["completion_rate"]
    # 2 completed / (2 completed + 1 overdue open); cancelled and future tasks excluded (BR-023, BR-024)
    assert (rate["numerator"], rate["denominator"], rate["value"]) == (2, 3, 0.6667)


def test_focus_distribution_and_month(api_client, user):
    cat = api_client.get("/api/v1/categories/").json()["results"][0]
    start = now() - timedelta(hours=3)
    api_client.post(
        "/api/v1/time-entries/",
        {
            "started_at": start.isoformat(),
            "ended_at": (start + timedelta(hours=1)).isoformat(),
            "is_focus": True,
            "category_id": cat["id"],
        },
        format="json",
    )
    body = api_client.get("/api/v1/analytics/monthly/").json()
    assert body["time"]["focus_hours"]["value"] == 1.0
    assert body["time"]["distribution"][0]["minutes"] == 60
    assert body["time"]["distribution"][0]["share"] == 1.0
    assert body["previous"]["focus_hours"] == 0


def test_metric_shape():
    assert metric("k", 1, 4)["value"] == 0.25
    assert metric("k", 0, 0)["reason"] == "NO_DATA"


def test_isolation(api_client, other_client):
    t = api_client.post("/api/v1/tasks/", {"title": "мой"}, format="json").json()
    api_client.post(f"/api/v1/tasks/{t['id']}/complete/")
    assert other_client.get("/api/v1/analytics/daily/").json()["tasks"]["completed"] == 0
