from datetime import timedelta

import pytest

from apps.tasks.models import Task
from common.time import local_today, now

pytestmark = pytest.mark.django_db


def week_start():
    today = local_today("Asia/Bishkek")
    return today - timedelta(days=today.isoweekday() - 1)


def test_review_flow(api_client, user):
    done = api_client.post("/api/v1/tasks/", {"title": "Готово"}, format="json").json()
    api_client.post(f"/api/v1/tasks/{done['id']}/complete/")
    carry = api_client.post("/api/v1/tasks/", {"title": "Перенести"}, format="json").json()
    drop = api_client.post("/api/v1/tasks/", {"title": "Отменить"}, format="json").json()
    later = api_client.post("/api/v1/tasks/", {"title": "Когда-нибудь"}, format="json").json()
    Task.objects.filter(id__in=[carry["id"], drop["id"], later["id"]]).update(
        due_at=now() - timedelta(hours=1)
    )

    res = api_client.post("/api/v1/reviews/", {}, format="json")
    assert res.status_code == 201
    review = res.json()
    assert review["status"] == "DRAFT"
    assert review["week_start"] == week_start().isoformat()
    assert review["stats_snapshot"]["tasks"]["completed"] == 1
    # idempotent per week
    assert api_client.post("/api/v1/reviews/", {}, format="json").json()["id"] == review["id"]

    unfinished = api_client.get(f"/api/v1/reviews/{review['id']}/unfinished-tasks/").json()["results"]
    assert {t["id"] for t in unfinished} == {carry["id"], drop["id"], later["id"]}

    res = api_client.put(
        f"/api/v1/reviews/{review['id']}/task-decisions/",
        {
            "decisions": [
                {"task_id": carry["id"], "decision": "CARRY_OVER"},
                {"task_id": drop["id"], "decision": "CANCEL"},
                {"task_id": later["id"], "decision": "BACKLOG"},
            ]
        },
        format="json",
    )
    assert res.status_code == 200, res.json()
    api_client.patch(
        f"/api/v1/reviews/{review['id']}/",
        {"wins": "Сдал лабу", "week_rating": 8, "next_week_focus": "Резюме"},
        format="json",
    )
    done_review = api_client.post(f"/api/v1/reviews/{review['id']}/complete/").json()
    assert done_review["status"] == "COMPLETED" and done_review["wins"] == "Сдал лабу"

    statuses = dict(Task.objects.filter(user=user).values_list("title", "status"))
    assert statuses["Перенести"] == "POSTPONED"
    assert statuses["Отменить"] == "CANCELLED"
    assert statuses["Когда-нибудь"] == "BACKLOG"

    locked = api_client.patch(f"/api/v1/reviews/{review['id']}/", {"wins": "x"}, format="json")
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "REVIEW_ALREADY_COMPLETED"
    assert api_client.get("/api/v1/reviews/").json()["results"][0]["status"] == "COMPLETED"


def test_rules(api_client, other_client):
    wrong = api_client.post(
        "/api/v1/reviews/", {"week_start": (week_start() + timedelta(days=1)).isoformat()}, format="json"
    )
    assert wrong.status_code == 400
    review = api_client.post("/api/v1/reviews/", {}, format="json").json()
    task = api_client.post(
        "/api/v1/tasks/", {"title": "будущее", "due_date": "2099-01-01"}, format="json"
    ).json()
    res = api_client.put(
        f"/api/v1/reviews/{review['id']}/task-decisions/",
        {"decisions": [{"task_id": task["id"], "decision": "CANCEL"}]},
        format="json",
    )
    assert res.status_code == 400
    for method, url in [
        ("get", f"/api/v1/reviews/{review['id']}/"),
        ("patch", f"/api/v1/reviews/{review['id']}/"),
        ("post", f"/api/v1/reviews/{review['id']}/complete/"),
    ]:
        assert getattr(other_client, method)(url, {}, format="json").status_code == 404
