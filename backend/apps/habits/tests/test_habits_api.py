from datetime import timedelta

import pytest

from apps.habits.models import HabitLog, HabitLogRevision, HabitSchedule
from common.time import local_today

pytestmark = pytest.mark.django_db
TZ = "Asia/Bishkek"


def today():
    return local_today(TZ)


def create(client, **payload):
    payload.setdefault("name", "Чтение")
    payload.setdefault("start_date", (today() - timedelta(days=10)).isoformat())
    res = client.post("/api/v1/habits/", payload, format="json")
    assert res.status_code == 201, res.json()
    return res.json()


def log(client, habit_id, **payload):
    return client.post(f"/api/v1/habits/{habit_id}/logs/", payload, format="json")


class TestCreate:
    def test_boolean_daily(self, api_client):
        h = create(api_client)
        assert h["tracking_type"] == "BOOLEAN"
        assert h["schedule"]["frequency_type"] == "DAILY"
        assert len(h["schedules"]) == 1

    def test_duration_forces_minutes_and_needs_target(self, api_client):
        res = api_client.post(
            "/api/v1/habits/", {"name": "Спорт", "tracking_type": "DURATION", "unit": "часы"}, format="json"
        )
        assert res.status_code == 400
        h = create(api_client, name="Спорт", tracking_type="DURATION", schedule={"target_value": "30"})
        assert h["unit"] == "min"

    @pytest.mark.parametrize(
        "payload,field",
        [
            ({"tracking_type": "SCALE"}, "scale_max"),
            ({"schedule": {"frequency_type": "WEEKDAYS"}}, "weekdays_mask"),
            ({"schedule": {"frequency_type": "TIMES_PER_WEEK", "times_per_period": 9}}, "times_per_period"),
            ({"schedule": {"frequency_type": "EVERY_N_DAYS", "interval_days": 1}}, "interval_days"),
        ],
    )
    def test_validation(self, api_client, payload, field):
        res = api_client.post("/api/v1/habits/", {"name": "x", **payload}, format="json")
        assert res.status_code == 400
        assert field in res.json()["error"]["details"]


class TestLogs:
    def test_boolean_once_per_day(self, api_client):
        h = create(api_client)
        assert log(api_client, h["id"]).status_code == 201
        res = log(api_client, h["id"])
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "HABIT_ALREADY_LOGGED"

    def test_quantity_sums_into_done(self, api_client):
        h = create(
            api_client, name="Вода", tracking_type="QUANTITY", unit="стаканов", schedule={"target_value": "8"}
        )
        a = log(api_client, h["id"], value="5").json()
        assert a["status"] == "PARTIAL"
        assert log(api_client, h["id"], value="3").json()["status"] == "DONE"
        assert HabitLog.objects.get(id=a["id"]).status == "DONE"  # recomputed for the whole day
        assert a["target_value_snapshot"] == "8.00"

    def test_skip_cannot_coexist_with_done(self, api_client):
        h = create(api_client, tracking_type="QUANTITY", schedule={"target_value": "8"})
        log(api_client, h["id"], value="1")
        assert log(api_client, h["id"], status="SKIPPED").status_code == 409

    def test_scale_bounds_and_future(self, api_client):
        h = create(
            api_client,
            name="Настроение",
            tracking_type="SCALE",
            scale_min=1,
            scale_max=5,
            schedule={"target_value": "3"},
        )
        assert log(api_client, h["id"], value="7").status_code == 400
        assert log(api_client, h["id"], value="2").json()["status"] == "PARTIAL"
        tomorrow = (today() + timedelta(days=1)).isoformat()
        assert log(api_client, h["id"], log_date=tomorrow, value="3").status_code == 400

    def test_edit_and_void_keep_history(self, api_client):
        h = create(api_client, tracking_type="QUANTITY", schedule={"target_value": "8"})
        entry = log(api_client, h["id"], value="2").json()
        res = api_client.patch(f"/api/v1/habit-logs/{entry['id']}/", {"value": "9"}, format="json")
        assert res.json()["status"] == "DONE"
        assert api_client.delete(f"/api/v1/habit-logs/{entry['id']}/").status_code == 204
        assert HabitLog.objects.get(id=entry["id"]).is_voided
        assert HabitLogRevision.objects.filter(habit_log_id=entry["id"]).count() == 2
        assert log(api_client, h["id"], value="1").status_code == 201  # voided record frees the day

    def test_type_locked_after_logs(self, api_client):
        h = create(api_client)
        log(api_client, h["id"])
        res = api_client.patch(f"/api/v1/habits/{h['id']}/", {"tracking_type": "QUANTITY"}, format="json")
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "HABIT_TYPE_LOCKED"


class TestScheduleVersions:
    def test_frequency_change_creates_new_version(self, api_client):
        h = create(api_client)
        res = api_client.patch(
            f"/api/v1/habits/{h['id']}/",
            {"schedule": {"frequency_type": "WEEKDAYS", "weekdays_mask": 31}},
            format="json",
        )
        assert res.status_code == 200, res.json()
        versions = HabitSchedule.objects.filter(habit_id=h["id"]).order_by("valid_from")
        assert [v.frequency_type for v in versions] == ["DAILY", "WEEKDAYS"]
        assert versions[0].valid_to == today() - timedelta(days=1)
        assert versions[1].valid_from == today()

    def test_same_day_change_updates_in_place(self, api_client):
        h = create(api_client, start_date=today().isoformat())
        api_client.patch(
            f"/api/v1/habits/{h['id']}/",
            {"schedule": {"frequency_type": "EVERY_N_DAYS", "interval_days": 2}},
            format="json",
        )
        assert HabitSchedule.objects.filter(habit_id=h["id"]).count() == 1


class TestTodayStatsHistory:
    def test_today_and_stats(self, api_client):
        h = create(api_client, start_date=(today() - timedelta(days=3)).isoformat())
        for n in (3, 2, 1):
            log(api_client, h["id"], log_date=(today() - timedelta(days=n)).isoformat())
        body = api_client.get("/api/v1/habits/today/").json()
        item = next(i for i in body["results"] if i["habit"]["id"] == h["id"])
        assert item["planned"] is True and item["status"] is None
        assert item["current_streak"] == 3
        stats = api_client.get(f"/api/v1/habits/{h['id']}/stats/?period=year").json()
        assert stats["best_streak"] == 3
        assert stats["consistency"] == 1.0

    def test_history_days(self, api_client):
        h = create(api_client)
        log(api_client, h["id"])
        body = api_client.get(f"/api/v1/habits/{h['id']}/history/").json()
        assert len(body["days"]) == 30
        assert body["days"][-1]["status"] == "DONE"
        assert len(body["logs"]) == 1

    def test_pause_and_archive(self, api_client):
        h = create(api_client)
        res = api_client.post(
            f"/api/v1/habits/{h['id']}/pauses/",
            {"start_date": today().isoformat(), "reason": "Отпуск"},
            format="json",
        )
        assert res.status_code == 201
        overlap = api_client.post(
            f"/api/v1/habits/{h['id']}/pauses/", {"start_date": today().isoformat()}, format="json"
        )
        assert overlap.status_code == 400
        item = next(
            i
            for i in api_client.get("/api/v1/habits/today/").json()["results"]
            if i["habit"]["id"] == h["id"]
        )
        assert item["paused"] is True
        assert api_client.delete(f"/api/v1/habit-pauses/{res.json()['id']}/").status_code == 204
        api_client.post(f"/api/v1/habits/{h['id']}/archive/")
        assert api_client.get("/api/v1/habits/").json()["results"] == []
        assert log(api_client, h["id"]).status_code == 400


def test_isolation(api_client, other_client):
    h = create(api_client)
    entry = log(api_client, h["id"]).json()
    for method, url in [
        ("get", f"/api/v1/habits/{h['id']}/"),
        ("patch", f"/api/v1/habits/{h['id']}/"),
        ("post", f"/api/v1/habits/{h['id']}/logs/"),
        ("get", f"/api/v1/habits/{h['id']}/stats/"),
        ("patch", f"/api/v1/habit-logs/{entry['id']}/"),
        ("delete", f"/api/v1/habit-logs/{entry['id']}/"),
    ]:
        assert getattr(other_client, method)(url, {}, format="json").status_code == 404, url
    assert other_client.get("/api/v1/habits/").json()["results"] == []
