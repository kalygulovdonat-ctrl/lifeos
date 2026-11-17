from decimal import Decimal

import pytest

from apps.goals import progress
from apps.goals.models import GoalProgress

pytestmark = pytest.mark.django_db


def create(client, **payload):
    payload.setdefault("title", "Выучить английский до B2")
    res = client.post("/api/v1/goals/", payload, format="json")
    assert res.status_code == 201, res.json()
    return res.json()


class TestProgress:
    def test_metric_decreasing_goal(self, api_client):
        g = create(
            api_client,
            title="Сбросить вес",
            progress_type="METRIC",
            start_value="80",
            target_value="72",
            metric_unit="кг",
        )
        assert g["progress_pct"] == "0.00"
        res = api_client.post(f"/api/v1/goals/{g['id']}/progress/", {"value": "76"}, format="json")
        assert res.json()["progress_pct"] == "50.00"
        res = api_client.post(f"/api/v1/goals/{g['id']}/progress/", {"value": "70"}, format="json")
        assert res.json()["progress_pct"] == "100.00"
        assert res.json()["target_reached"] is True
        assert res.json()["status"] == "ACTIVE"  # 100% asks the user, never auto-completes (BR-045)

    def test_metric_requires_values(self, api_client):
        res = api_client.post("/api/v1/goals/", {"title": "x", "progress_type": "METRIC"}, format="json")
        assert res.status_code == 400

    def test_milestones_weighted_and_skipped(self, api_client):
        g = create(api_client, progress_type="MILESTONES")
        url = f"/api/v1/goals/{g['id']}/milestones/"
        a = api_client.post(url, {"title": "A1", "weight": "1"}, format="json").json()
        b = api_client.post(url, {"title": "A2", "weight": "3"}, format="json").json()
        c = api_client.post(url, {"title": "B1"}, format="json").json()
        api_client.post(f"/api/v1/milestones/{b['id']}/complete/")
        assert api_client.get(f"/api/v1/goals/{g['id']}/").json()["progress_pct"] == "60.00"
        api_client.patch(f"/api/v1/milestones/{c['id']}/", {"status": "SKIPPED"}, format="json")
        assert api_client.get(f"/api/v1/goals/{g['id']}/").json()["progress_pct"] == "75.00"
        api_client.delete(f"/api/v1/milestones/{a['id']}/")
        assert api_client.get(f"/api/v1/goals/{g['id']}/").json()["progress_pct"] == "100.00"

    def test_tasks_progress_follows_task_status(self, api_client):
        g = create(api_client, progress_type="TASKS")
        t1 = api_client.post("/api/v1/tasks/", {"title": "Урок 1"}, format="json").json()
        t2 = api_client.post("/api/v1/tasks/", {"title": "Урок 2"}, format="json").json()
        for t in (t1, t2):
            assert api_client.post(f"/api/v1/goals/{g['id']}/tasks/{t['id']}/").status_code == 200
        api_client.post(f"/api/v1/tasks/{t1['id']}/complete/")
        assert api_client.get(f"/api/v1/goals/{g['id']}/").json()["progress_pct"] == "50.00"
        api_client.post(f"/api/v1/tasks/{t2['id']}/status/", {"status": "CANCELLED"}, format="json")
        detail = api_client.get(f"/api/v1/goals/{g['id']}/").json()
        assert detail["progress_pct"] == "100.00"
        assert api_client.get(f"/api/v1/tasks/{t1['id']}/").json()["goal_ids"] == [g["id"]]
        tasks = api_client.get(f"/api/v1/goals/{g['id']}/tasks/").json()["results"]
        assert {t["id"] for t in tasks} == {t1["id"], t2["id"]}
        api_client.delete(f"/api/v1/goals/{g['id']}/tasks/{t2['id']}/")
        history = api_client.get(f"/api/v1/goals/{g['id']}/progress-history/").json()
        assert [p["progress_pct"] for p in history["progress"]] == ["50.00", "100.00"]

    def test_manual_progress_is_percentage(self, api_client):
        g = create(api_client, progress_type="MANUAL")
        assert (
            api_client.post(f"/api/v1/goals/{g['id']}/progress/", {"value": "130"}, format="json").status_code
            == 400
        )
        assert (
            api_client.post(f"/api/v1/goals/{g['id']}/progress/", {"value": "40"}, format="json").json()[
                "progress_pct"
            ]
            == "40.00"
        )
        auto = create(api_client, progress_type="MILESTONES")
        res = api_client.post(f"/api/v1/goals/{auto['id']}/progress/", {"value": "10"}, format="json")
        assert res.status_code == 409

    def test_pure_formulas(self):
        assert progress.metric(Decimal(0), Decimal(10), Decimal(15)) == Decimal("100.00")
        assert progress.metric(Decimal(0), Decimal(10), Decimal(-5)) == Decimal("0.00")
        assert progress.milestones([]) == Decimal(0)


class TestStatusAndTree:
    def test_status_actions(self, api_client):
        g = create(api_client)
        assert (
            api_client.post(f"/api/v1/goals/{g['id']}/status/", {"action": "PAUSE"}, format="json").json()[
                "status"
            ]
            == "PAUSED"
        )
        bad = api_client.post(f"/api/v1/goals/{g['id']}/status/", {"action": "PAUSE"}, format="json")
        assert bad.status_code == 409
        done = api_client.post(
            f"/api/v1/goals/{g['id']}/status/", {"action": "COMPLETE"}, format="json"
        ).json()
        assert done["status"] == "COMPLETED" and done["completed_at"]
        history = api_client.get(f"/api/v1/goals/{g['id']}/progress-history/").json()["status"]
        assert [h["to_status"] for h in history] == ["ACTIVE", "PAUSED", "COMPLETED"]

    def test_tree_and_cycles(self, api_client):
        vision = create(api_client, title="Стать разработчиком", level="VISION")
        year = create(api_client, title="Год", level="YEARLY", parent_id=vision["id"])
        create(api_client, title="Квартал", level="QUARTERLY", parent_id=year["id"])
        tree = api_client.get("/api/v1/goals/?tree=true").json()["results"]
        assert len(tree) == 1
        assert tree[0]["children"][0]["children"][0]["title"] == "Квартал"
        cycle = api_client.patch(f"/api/v1/goals/{vision['id']}/", {"parent_id": year["id"]}, format="json")
        assert cycle.status_code == 400
        assert api_client.delete(f"/api/v1/goals/{year['id']}/").status_code == 204
        roots = api_client.get("/api/v1/goals/?tree=true").json()["results"]
        assert {r["title"] for r in roots} == {"Стать разработчиком", "Квартал"}

    def test_target_date_after_start(self, api_client):
        res = api_client.post(
            "/api/v1/goals/",
            {"title": "x", "start_date": "2026-11-10", "target_date": "2026-11-01"},
            format="json",
        )
        assert res.status_code == 400


def test_isolation(api_client, other_client):
    g = create(api_client, progress_type="MILESTONES")
    m = api_client.post(f"/api/v1/goals/{g['id']}/milestones/", {"title": "m"}, format="json").json()
    own_task = other_client.post("/api/v1/tasks/", {"title": "мой"}, format="json").json()
    for method, url in [
        ("get", f"/api/v1/goals/{g['id']}/"),
        ("patch", f"/api/v1/goals/{g['id']}/"),
        ("delete", f"/api/v1/goals/{g['id']}/"),
        ("post", f"/api/v1/goals/{g['id']}/milestones/"),
        ("post", f"/api/v1/goals/{g['id']}/tasks/{own_task['id']}/"),
        ("patch", f"/api/v1/milestones/{m['id']}/"),
        ("post", f"/api/v1/milestones/{m['id']}/complete/"),
    ]:
        assert getattr(other_client, method)(url, {}, format="json").status_code == 404, url
    # nor can the owner link someone else's task
    assert api_client.post(f"/api/v1/goals/{g['id']}/tasks/{own_task['id']}/").status_code == 404
    assert GoalProgress.objects.filter(goal_id=g["id"]).count() == 0
