"""User data isolation (BR-001, BR-002, PRD §12: "user A cannot read user B's data").

Every owner-scoped endpoint must answer 404 for another user's object id, and lists must
never contain foreign rows. Add each new module's endpoints to OWNED_ENDPOINTS.
"""

from datetime import UTC, datetime, timedelta

import pytest

from apps.accounts.models import Category, Tag
from apps.schedule.models import Event, EventSeries
from apps.tasks.models import Subtask, Task

OWNED_ENDPOINTS = [
    ("/api/v1/categories/", lambda user: Category.objects.filter(user=user).first()),
    ("/api/v1/tags/", lambda user: Tag.objects.create(user=user, name="secret-tag")),
    ("/api/v1/tasks/", lambda user: Task.objects.create(user=user, title="secret task")),
]

START = datetime(2026, 11, 18, 4, tzinfo=UTC)


@pytest.mark.django_db
@pytest.mark.parametrize("base,factory", OWNED_ENDPOINTS, ids=[e[0] for e in OWNED_ENDPOINTS])
class TestIsolation:
    def test_foreign_object_is_not_found(self, base, factory, user, other_client):
        obj = factory(user)
        url = f"{base}{obj.id}/"
        for method in ("get", "patch", "delete"):
            res = getattr(other_client, method)(url, {}, format="json")
            assert res.status_code == 404, f"{method.upper()} {url} -> {res.status_code}"
            assert res.json()["error"]["code"] == "NOT_FOUND"
        assert type(obj).objects.filter(id=obj.id).exists()

    def test_list_excludes_foreign_rows(self, base, factory, user, other_client):
        obj = factory(user)
        ids = {row["id"] for row in other_client.get(base).json()["results"]}
        assert str(obj.id) not in ids

    def test_anonymous_is_rejected(self, base, factory, anon_client):
        assert anon_client.get(base).status_code == 401


@pytest.mark.django_db
def test_cannot_create_row_for_another_user(api_client, user, other_user):
    res = api_client.post("/api/v1/tags/", {"name": "x", "user": str(other_user.id)})
    assert res.status_code == 201
    assert Tag.objects.get(id=res.json()["id"]).user_id == user.id


@pytest.mark.django_db
def test_schedule_and_subtasks_are_isolated(user, other_client):
    event = Event.objects.create(
        user=user, title="secret", start_at=START, end_at=START + timedelta(hours=1), timezone="UTC"
    )
    series = EventSeries.objects.create(
        user=user, title="secret", dtstart_at=START, duration_minutes=60, rrule="FREQ=DAILY", timezone="UTC"
    )
    task = Task.objects.create(user=user, title="secret task")
    sub = Subtask.objects.create(user=user, task=task, title="secret sub")
    epoch = int(START.timestamp())
    for method, url in [
        ("get", f"/api/v1/events/{event.id}/"),
        ("patch", f"/api/v1/events/{event.id}/"),
        ("delete", f"/api/v1/events/{event.id}/"),
        ("post", f"/api/v1/events/{event.id}/status/"),
        ("get", f"/api/v1/event-series/{series.id}/"),
        ("delete", f"/api/v1/event-series/{series.id}/"),
        ("delete", f"/api/v1/event-series/{series.id}/occurrences/{epoch}/"),
        ("get", f"/api/v1/tasks/{task.id}/subtasks/"),
        ("post", f"/api/v1/tasks/{task.id}/schedule/"),
        ("patch", f"/api/v1/subtasks/{sub.id}/"),
        ("delete", f"/api/v1/subtasks/{sub.id}/"),
    ]:
        res = getattr(other_client, method)(url, {}, format="json")
        assert res.status_code == 404, f"{method.upper()} {url} -> {res.status_code}"
    listing = other_client.get("/api/v1/events/?from=2026-11-18&to=2026-11-18").json()["results"]
    assert listing == []
    assert other_client.get("/api/v1/dashboard/?date=2026-11-18").json()["schedule"] == []
    assert Event.objects.filter(id=event.id).exists() and Subtask.objects.filter(id=sub.id).exists()


@pytest.mark.django_db
def test_cannot_link_foreign_task_to_event(api_client, other_user):
    foreign = Task.objects.create(user=other_user, title="theirs")
    res = api_client.post(
        "/api/v1/events/",
        {
            "title": "x",
            "start_at": "2026-11-18T10:00:00Z",
            "end_at": "2026-11-18T11:00:00Z",
            "task_id": str(foreign.id),
        },
        format="json",
    )
    assert res.status_code == 400
    assert "task_id" in res.json()["error"]["details"]
