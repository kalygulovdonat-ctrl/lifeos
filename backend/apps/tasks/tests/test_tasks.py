from datetime import timedelta

import pytest

from apps.accounts.models import Category, Tag
from apps.tasks.models import Subtask, Task, TaskStatusChange
from common.time import now

pytestmark = pytest.mark.django_db


def create(client, **payload):
    payload.setdefault("title", "Сдать лабораторную")
    res = client.post("/api/v1/tasks/", payload, format="json")
    assert res.status_code == 201, res.json()
    return res.json()


class TestCreate:
    def test_defaults_and_history(self, api_client, user):
        body = create(api_client)
        assert body["status"] == "TODO"
        assert body["priority"] == "MEDIUM"
        assert body["in_inbox"] is False
        assert body["subtasks"] == []
        change = TaskStatusChange.objects.get(task_id=body["id"])
        assert (change.from_status, change.to_status) == (None, "TODO")

    def test_due_date_is_end_of_local_day(self, api_client):
        body = create(api_client, due_date="2026-11-20")
        assert body["due_has_time"] is False
        assert body["due_date"] == "2026-11-20"
        # Asia/Bishkek is UTC+6: end of 20 Nov local = 20 Nov 17:59:59.999999 UTC
        assert body["due_at"].startswith("2026-11-20T17:59:59")

    def test_due_at_requires_offset(self, api_client):
        res = api_client.post(
            "/api/v1/tasks/", {"title": "x", "due_at": "2026-11-20T10:00:00"}, format="json"
        )
        assert res.status_code == 400
        assert "due_at" in res.json()["error"]["details"]

    def test_with_subtasks_tags_category(self, api_client, user):
        tag = Tag.objects.create(user=user, name="uni")
        cat = Category.objects.filter(user=user).first()
        body = create(
            api_client, subtasks=["Прочитать", "Написать"], tag_ids=[str(tag.id)], category_id=str(cat.id)
        )
        assert [s["title"] for s in body["subtasks"]] == ["Прочитать", "Написать"]
        assert body["subtasks_total"] == 2
        assert body["tag_ids"] == [str(tag.id)]
        assert body["category_id"] == str(cat.id)

    def test_foreign_category_and_tag_rejected(self, api_client, other_user):
        cat = Category.objects.filter(user=other_user).first()
        tag = Tag.objects.create(user=other_user, name="secret")
        res = api_client.post(
            "/api/v1/tasks/",
            {"title": "x", "category_id": str(cat.id), "tag_ids": [str(tag.id)]},
            format="json",
        )
        assert res.status_code == 400
        details = res.json()["error"]["details"]
        assert "category_id" in details and "tag_ids" in details

    @pytest.mark.parametrize("bad", [{"title": "   "}, {"title": "x", "status": "COMPLETED"}])
    def test_validation(self, api_client, bad):
        res = api_client.post("/api/v1/tasks/", bad, format="json")
        assert res.status_code == 400

    def test_idempotent(self, api_client, user):
        headers = {"HTTP_IDEMPOTENCY_KEY": "task-key-1"}
        a = api_client.post("/api/v1/tasks/", {"title": "Один раз"}, format="json", **headers)
        b = api_client.post("/api/v1/tasks/", {"title": "Один раз"}, format="json", **headers)
        assert a.json()["id"] == b.json()["id"]
        assert Task.objects.filter(user=user).count() == 1


class TestInbox:
    def test_quick_capture_and_triage(self, api_client):
        res = api_client.post("/api/v1/tasks/quick/", {"title": "Идея"}, format="json")
        assert res.status_code == 201
        task = res.json()
        assert task["in_inbox"] is True
        inbox = api_client.get("/api/v1/tasks/?inbox=true").json()
        assert [t["id"] for t in inbox["results"]] == [task["id"]]

        res = api_client.post(f"/api/v1/tasks/{task['id']}/triage/")
        assert res.json()["in_inbox"] is False
        assert api_client.get("/api/v1/tasks/?inbox=true").json()["count"] == 0

    def test_setting_due_date_triages(self, api_client):
        task = api_client.post("/api/v1/tasks/quick/", {"title": "Идея"}, format="json").json()
        res = api_client.patch(f"/api/v1/tasks/{task['id']}/", {"due_date": "2026-12-01"}, format="json")
        assert res.json()["in_inbox"] is False

    def test_completing_leaves_inbox(self, api_client):
        task = api_client.post("/api/v1/tasks/quick/", {"title": "Идея"}, format="json").json()
        api_client.post(f"/api/v1/tasks/{task['id']}/complete/")
        assert api_client.get("/api/v1/tasks/?inbox=true").json()["count"] == 0


class TestStatus:
    def test_complete_and_reopen(self, api_client):
        task = create(api_client)
        res = api_client.post(f"/api/v1/tasks/{task['id']}/complete/")
        assert res.status_code == 200
        assert res.json()["status"] == "COMPLETED"
        assert res.json()["completed_at"]
        res = api_client.post(f"/api/v1/tasks/{task['id']}/status/", {"status": "TODO"}, format="json")
        assert res.json()["status"] == "TODO"
        assert res.json()["completed_at"] is None

    @pytest.mark.parametrize(
        "path",
        [
            ["COMPLETED", "IN_PROGRESS"],
            ["COMPLETED", "CANCELLED"],
            ["CANCELLED", "IN_PROGRESS"],
            ["BACKLOG", "POSTPONED"],
        ],
    )
    def test_invalid_transitions(self, api_client, path):
        task = create(api_client)
        first, second = path
        api_client.post(
            f"/api/v1/tasks/{task['id']}/status/", {"status": first, "reason": "r"}, format="json"
        )
        res = api_client.post(
            f"/api/v1/tasks/{task['id']}/status/", {"status": second, "reason": "r"}, format="json"
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"

    def test_postpone_requires_date_or_reason(self, api_client):
        task = create(api_client)
        res = api_client.post(f"/api/v1/tasks/{task['id']}/postpone/", {}, format="json")
        assert res.status_code == 400

    def test_postpone_moves_due_and_logs(self, api_client):
        task = create(api_client, due_date="2026-11-20")
        res = api_client.post(
            f"/api/v1/tasks/{task['id']}/postpone/",
            {"new_due_date": "2026-11-25", "reason": "Заболел"},
            format="json",
        )
        body = res.json()
        assert body["status"] == "POSTPONED"
        assert body["due_date"] == "2026-11-25"
        assert body["postponed_count"] == 1
        history = api_client.get(f"/api/v1/tasks/{task['id']}/history/").json()["results"]
        assert history[-1]["reason"] == "Заболел"
        assert history[-1]["old_due_at"].startswith("2026-11-20")

    def test_cancel_sets_cancelled_at(self, api_client):
        task = create(api_client)
        res = api_client.post(f"/api/v1/tasks/{task['id']}/status/", {"status": "CANCELLED"}, format="json")
        assert res.json()["cancelled_at"]


class TestListAndFilters:
    def test_filters(self, api_client, user):
        a = create(api_client, title="Alpha report", priority="HIGH")
        create(api_client, title="Beta", priority="LOW")
        c = create(api_client, title="Gamma")
        api_client.post(f"/api/v1/tasks/{c['id']}/complete/")

        def ids(qs):
            return {t["id"] for t in api_client.get(f"/api/v1/tasks/?{qs}").json()["results"]}

        assert ids("priority=HIGH") == {a["id"]}
        assert ids("q=report") == {a["id"]}
        assert ids("status=COMPLETED") == {c["id"]}
        assert len(ids("status=OPEN")) == 2
        res = api_client.get("/api/v1/tasks/?status=NOPE")
        assert res.status_code == 400

    def test_ordering_by_priority(self, api_client):
        create(api_client, title="low", priority="LOW")
        create(api_client, title="urgent", priority="URGENT")
        titles = [t["title"] for t in api_client.get("/api/v1/tasks/?ordering=-priority").json()["results"]]
        assert titles[0] == "urgent"

    def test_overdue(self, api_client, user):
        task = create(api_client)
        Task.objects.filter(id=task["id"]).update(due_at=now() - timedelta(days=2))
        body = api_client.get("/api/v1/tasks/?overdue=true").json()
        assert body["results"][0]["is_overdue"] is True

    def test_archive_restore_delete(self, api_client):
        task = create(api_client)
        api_client.post(f"/api/v1/tasks/{task['id']}/archive/")
        assert api_client.get("/api/v1/tasks/").json()["count"] == 0
        assert api_client.get("/api/v1/tasks/?archived=true").json()["count"] == 1
        api_client.post(f"/api/v1/tasks/{task['id']}/restore/")
        assert api_client.delete(f"/api/v1/tasks/{task['id']}/").status_code == 204
        assert api_client.get(f"/api/v1/tasks/{task['id']}/").status_code == 404
        # history survives soft delete (BR-026)
        assert TaskStatusChange.objects.filter(task_id=task["id"]).exists()


class TestSubtasks:
    def test_crud_and_reorder(self, api_client):
        task = create(api_client)
        url = f"/api/v1/tasks/{task['id']}/subtasks/"
        a = api_client.post(url, {"title": "A"}, format="json").json()
        b = api_client.post(url, {"title": "B"}, format="json").json()
        res = api_client.patch(f"/api/v1/subtasks/{a['id']}/", {"is_done": True}, format="json")
        assert res.json()["is_done"] is True and res.json()["done_at"]
        res = api_client.post(f"{url}reorder/", {"ids": [b["id"], a["id"]]}, format="json")
        assert [s["title"] for s in res.json()["results"]] == ["B", "A"]
        detail = api_client.get(f"/api/v1/tasks/{task['id']}/").json()
        assert (detail["subtasks_total"], detail["subtasks_done"]) == (2, 1)
        assert api_client.delete(f"/api/v1/subtasks/{a['id']}/").status_code == 204
        assert Subtask.objects.count() == 1

    def test_reorder_needs_all_ids(self, api_client):
        task = create(api_client, subtasks=["A", "B"])
        res = api_client.post(
            f"/api/v1/tasks/{task['id']}/subtasks/reorder/",
            {"ids": [task["subtasks"][0]["id"]]},
            format="json",
        )
        assert res.status_code == 400


class TestIsolation:
    def test_other_user_gets_404(self, api_client, other_client):
        task = create(api_client, subtasks=["A"])
        sid = task["subtasks"][0]["id"]
        for method, url in [
            ("get", f"/api/v1/tasks/{task['id']}/"),
            ("patch", f"/api/v1/tasks/{task['id']}/"),
            ("delete", f"/api/v1/tasks/{task['id']}/"),
            ("post", f"/api/v1/tasks/{task['id']}/complete/"),
            ("get", f"/api/v1/tasks/{task['id']}/history/"),
            ("patch", f"/api/v1/subtasks/{sid}/"),
        ]:
            res = getattr(other_client, method)(url, {}, format="json")
            assert res.status_code == 404, (method, url)
        assert other_client.get("/api/v1/tasks/").json()["count"] == 0


class TestScheduleBlock:
    def test_creates_event_linked_to_task(self, api_client):
        task = create(api_client, title="Курсовая")
        res = api_client.post(
            f"/api/v1/tasks/{task['id']}/schedule/",
            {"start_at": "2026-11-18T15:00:00+06:00", "end_at": "2026-11-18T17:00:00+06:00"},
            format="json",
        )
        assert res.status_code == 201, res.json()
        body = res.json()
        assert body["task"] == {"id": task["id"], "title": "Курсовая"}
        assert body["time_type"] == "FOCUS"
        assert body["start_at"].startswith("2026-11-18T09:00:00")
