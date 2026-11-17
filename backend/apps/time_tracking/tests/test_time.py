from datetime import timedelta

import pytest

from apps.time_tracking.models import TimeEntry, TimeEntryPause, TimeEntryRevision
from apps.time_tracking.selectors import merged_seconds
from common.time import now

pytestmark = pytest.mark.django_db


def iso(dt):
    return dt.isoformat()


class TestTimer:
    def test_lifecycle(self, api_client):
        assert api_client.get("/api/v1/timer/").json() is None
        res = api_client.post(
            "/api/v1/timer/start/", {"description": "Курсовая", "is_focus": True}, format="json"
        )
        assert res.status_code == 201
        assert res.json()["status"] == "RUNNING"
        again = api_client.post("/api/v1/timer/start/", {}, format="json")
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "TIMER_ALREADY_RUNNING"

        assert api_client.post("/api/v1/timer/pause/").json()["status"] == "PAUSED"
        paused = api_client.get("/api/v1/timer/").json()
        assert paused["open_pause_at"]
        # pretend the pause lasted 10 minutes and the session started an hour ago
        entry = TimeEntry.objects.get(id=paused["id"])
        TimeEntry.objects.filter(id=entry.id).update(started_at=now() - timedelta(hours=1))
        TimeEntryPause.objects.filter(time_entry=entry).update(paused_at=now() - timedelta(minutes=10))
        assert api_client.post("/api/v1/timer/resume/").json()["status"] == "RUNNING"
        body = api_client.post("/api/v1/timer/stop/").json()
        assert body["status"] == "STOPPED"
        assert 49 * 60 <= body["duration_seconds"] <= 51 * 60
        assert api_client.get("/api/v1/timer/").json() is None

    def test_no_active_timer(self, api_client):
        for action in ("pause", "resume", "stop", "discard"):
            res = api_client.post(f"/api/v1/timer/{action}/")
            assert res.status_code == 409
            assert res.json()["error"]["code"] == "NO_ACTIVE_TIMER"

    def test_discard(self, api_client):
        api_client.post("/api/v1/timer/start/", {}, format="json")
        assert api_client.post("/api/v1/timer/discard/").status_code == 204
        assert TimeEntry.objects.count() == 0
        assert api_client.post("/api/v1/timer/start/", {}, format="json").status_code == 201

    def test_task_link_and_actual_minutes(self, api_client):
        task = api_client.post("/api/v1/tasks/", {"title": "Отчёт"}, format="json").json()
        start = now() - timedelta(hours=2)
        res = api_client.post(
            "/api/v1/time-entries/",
            {"task_id": task["id"], "started_at": iso(start), "ended_at": iso(start + timedelta(minutes=45))},
            format="json",
        )
        assert res.status_code == 201, res.json()
        assert res.json()["task"] == {"id": task["id"], "title": "Отчёт"}
        assert api_client.get(f"/api/v1/tasks/{task['id']}/").json()["actual_minutes"] == 45
        entries = api_client.get(f"/api/v1/tasks/{task['id']}/time-entries/").json()["results"]
        assert len(entries) == 1


class TestManual:
    def test_validation(self, api_client):
        start = now() - timedelta(hours=3)
        bad = [
            {"started_at": iso(start), "ended_at": iso(start)},
            {"started_at": iso(now()), "ended_at": iso(now() + timedelta(hours=1))},
            {"started_at": iso(now() - timedelta(hours=30)), "ended_at": iso(now() - timedelta(hours=2))},
        ]
        for payload in bad:
            assert api_client.post("/api/v1/time-entries/", payload, format="json").status_code == 400

    def test_duplicate_and_overlap(self, api_client):
        start = now() - timedelta(hours=3)
        payload = {"started_at": iso(start), "ended_at": iso(start + timedelta(hours=1))}
        assert api_client.post("/api/v1/time-entries/", payload, format="json").status_code == 201
        dup = api_client.post("/api/v1/time-entries/", payload, format="json")
        assert dup.status_code == 409
        assert dup.json()["error"]["code"] == "DUPLICATE_TIME_ENTRY"
        part = api_client.post(
            "/api/v1/time-entries/",
            {
                "started_at": iso(start + timedelta(minutes=30)),
                "ended_at": iso(start + timedelta(minutes=90)),
            },
            format="json",
        )
        assert part.status_code == 201
        assert part.json()["warnings"][0]["code"] == "TIME_ENTRY_OVERLAP"

    def test_edit_creates_revision_and_delete(self, api_client):
        start = now() - timedelta(hours=3)
        e = api_client.post(
            "/api/v1/time-entries/",
            {"started_at": iso(start), "ended_at": iso(start + timedelta(minutes=30))},
            format="json",
        ).json()
        res = api_client.patch(
            f"/api/v1/time-entries/{e['id']}/",
            {"ended_at": iso(start + timedelta(minutes=50)), "reason": "Забыл остановить"},
            format="json",
        )
        assert res.json()["duration_seconds"] == 50 * 60
        assert TimeEntryRevision.objects.get(time_entry_id=e["id"]).reason == "Забыл остановить"
        assert api_client.delete(f"/api/v1/time-entries/{e['id']}/").status_code == 204

    def test_list_total_merges_overlaps(self, api_client):
        start = now() - timedelta(hours=3)
        for a, b in ((0, 60), (30, 90)):
            api_client.post(
                "/api/v1/time-entries/",
                {
                    "started_at": iso(start + timedelta(minutes=a)),
                    "ended_at": iso(start + timedelta(minutes=b)),
                },
                format="json",
            )
        day = (now() - timedelta(days=1)).date().isoformat()
        tomorrow = (now() + timedelta(days=1)).date().isoformat()
        body = api_client.get(f"/api/v1/time-entries/?from={day}&to={tomorrow}").json()
        assert body["count"] == 2
        assert body["total_seconds"] == 90 * 60


def test_merged_seconds():
    t = now()
    assert (
        merged_seconds(
            [(t, t + timedelta(minutes=10)), (t + timedelta(minutes=5), t + timedelta(minutes=20))]
        )
        == 1200
    )
    assert merged_seconds([]) == 0


def test_plan_vs_actual(api_client):
    start = (now() - timedelta(hours=5)).replace(microsecond=0)
    task = api_client.post("/api/v1/tasks/", {"title": "Лаба"}, format="json").json()
    api_client.post(
        f"/api/v1/tasks/{task['id']}/schedule/",
        {"start_at": iso(start), "end_at": iso(start + timedelta(hours=2))},
        format="json",
    )
    api_client.post(
        "/api/v1/time-entries/",
        {
            "task_id": task["id"],
            "started_at": iso(start + timedelta(minutes=30)),
            "ended_at": iso(start + timedelta(hours=3)),
            "is_focus": True,
        },
        format="json",
    )
    day = (now() - timedelta(days=1)).date().isoformat()
    tomorrow = (now() + timedelta(days=1)).date().isoformat()
    body = api_client.get(f"/api/v1/time-entries/plan-vs-actual/?from={day}&to={tomorrow}").json()
    assert body["planned_minutes"] == 120
    assert body["matched_minutes"] == 90
    assert body["actual_minutes"] == 150
    assert body["unplanned_minutes"] == 60
    assert body["accuracy"] == 0.75


def test_isolation(api_client, other_client):
    start = now() - timedelta(hours=3)
    e = api_client.post(
        "/api/v1/time-entries/",
        {"started_at": iso(start), "ended_at": iso(start + timedelta(minutes=5))},
        format="json",
    ).json()
    api_client.post("/api/v1/timer/start/", {}, format="json")
    assert other_client.get("/api/v1/timer/").json() is None
    assert other_client.patch(f"/api/v1/time-entries/{e['id']}/", {}, format="json").status_code == 404
    assert other_client.delete(f"/api/v1/time-entries/{e['id']}/").status_code == 404
    assert other_client.post("/api/v1/timer/start/", {}, format="json").status_code == 201
