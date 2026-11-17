from datetime import timedelta

import pytest

from apps.notifications.models import Notification
from apps.wellness.models import StateCheckin
from apps.wellness.services import overload_check
from common.time import local_today, now

pytestmark = pytest.mark.django_db


def iso(dt):
    return dt.isoformat()


def test_checkins_and_summary(api_client):
    res = api_client.post("/api/v1/wellness/checkins/", {"mood": 7, "energy": 6, "stress": 3}, format="json")
    assert res.status_code == 201, res.json()
    assert api_client.post("/api/v1/wellness/checkins/", {}, format="json").status_code == 400
    assert api_client.post("/api/v1/wellness/checkins/", {"mood": 11}, format="json").status_code == 400
    api_client.post("/api/v1/wellness/checkins/", {"mood": 5}, format="json")
    body = api_client.get("/api/v1/wellness/summary/").json()
    assert body["mood"] == 6.0 and body["energy"] == 6.0 and body["checkins"] == 2
    assert len(body["series"]) == 30
    cid = res.json()["id"]
    assert (
        api_client.patch(f"/api/v1/wellness/checkins/{cid}/", {"stress": 9}, format="json").json()["stress"]
        == 9
    )
    assert api_client.delete(f"/api/v1/wellness/checkins/{cid}/").status_code == 204


def test_sleep_rules(api_client):
    end = now() - timedelta(hours=1)
    ok = api_client.post(
        "/api/v1/wellness/sleep/",
        {"sleep_start": iso(end - timedelta(hours=7)), "sleep_end": iso(end), "quality": 8},
        format="json",
    )
    assert ok.status_code == 201, ok.json()
    assert ok.json()["minutes"] == 420
    overlap = api_client.post(
        "/api/v1/wellness/sleep/",
        {"sleep_start": iso(end - timedelta(hours=3)), "sleep_end": iso(end + timedelta(minutes=30))},
        format="json",
    )
    assert overlap.status_code == 400
    too_long = api_client.post(
        "/api/v1/wellness/sleep/",
        {"sleep_start": iso(end - timedelta(days=3)), "sleep_end": iso(end - timedelta(days=2))},
        format="json",
    )
    assert too_long.status_code == 400


def test_journal_mood_goes_to_checkin(api_client):
    res = api_client.post("/api/v1/journal/", {"body": "день", "mood": 8, "energy": 4}, format="json")
    assert res.status_code == 201, res.json()
    entry = res.json()
    assert (entry["mood"], entry["energy"]) == (8, 4)
    checkin = StateCheckin.objects.get(journal_entry_id=entry["id"])
    assert checkin.source == "JOURNAL"
    res = api_client.patch(f"/api/v1/journal/{entry['id']}/", {"mood": None, "energy": None}, format="json")
    assert res.json()["mood"] is None
    assert not StateCheckin.objects.filter(journal_entry_id=entry["id"]).exists()


def test_overload_observation_once_per_three_days(api_client, user):
    today = local_today("Asia/Bishkek")
    for n in range(1, 6):
        end = now() - timedelta(days=n)
        api_client.post(
            "/api/v1/wellness/sleep/",
            {"sleep_start": iso(end - timedelta(hours=5)), "sleep_end": iso(end)},
            format="json",
        )
    assert overload_check(user) is True
    assert overload_check(user) is False
    note = Notification.objects.get(user=user, type="OVERLOAD_WARNING")
    assert "SHORT_SLEEP" in note.params["signals"]
    assert today


def test_isolation(api_client, other_client):
    c = api_client.post("/api/v1/wellness/checkins/", {"mood": 5}, format="json").json()
    assert other_client.patch(f"/api/v1/wellness/checkins/{c['id']}/", {}, format="json").status_code == 404
    assert other_client.get("/api/v1/wellness/summary/").json()["checkins"] == 0
