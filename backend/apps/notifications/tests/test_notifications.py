from datetime import datetime, time, timedelta

import pytest

from apps.notifications.models import Notification, Reminder
from apps.notifications.services import dispatch_due
from common.time import local_today, now

pytestmark = pytest.mark.django_db


def test_event_reminder_fires_once(api_client, user):
    start = (now() + timedelta(minutes=10)).replace(second=0, microsecond=0)
    api_client.post(
        "/api/v1/events/",
        {
            "title": "Пара",
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
            "reminder_minutes": 15,
        },
        format="json",
    )
    assert dispatch_due() == 1
    assert dispatch_due() == 0  # idempotent: the unique reminder key blocks a second notification
    note = Notification.objects.get(user=user)
    assert note.type == "REMINDER" and note.params["title"] == "Пара"
    assert Reminder.objects.count() == 1


def test_series_reminder(api_client, user):
    start = (now() + timedelta(minutes=5)).replace(second=0, microsecond=0)
    api_client.post(
        "/api/v1/events/",
        {
            "title": "Зарядка",
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(minutes=20)).isoformat(),
            "reminder_minutes": 10,
            "recurrence": {"freq": "DAILY"},
        },
        format="json",
    )
    assert dispatch_due() == 1


def test_habit_reminder_skips_logged(api_client, user):
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Bishkek")
    local = now().astimezone(tz) - timedelta(minutes=5)
    if local.date() != local_today("Asia/Bishkek"):
        pytest.skip("too close to local midnight")
    h = api_client.post(
        "/api/v1/habits/",
        {"name": "Вода", "reminder_time": time(local.hour, local.minute).isoformat()},
        format="json",
    ).json()
    assert dispatch_due() == 1
    h2 = api_client.post(
        "/api/v1/habits/",
        {"name": "Чтение", "reminder_time": time(local.hour, local.minute).isoformat()},
        format="json",
    ).json()
    api_client.post(f"/api/v1/habits/{h2['id']}/logs/", {}, format="json")
    assert dispatch_due() == 0
    assert h


def test_api_and_goal_notification(api_client, user, other_client):
    goal = api_client.post(
        "/api/v1/goals/", {"title": "Цель", "progress_type": "MANUAL"}, format="json"
    ).json()
    api_client.post(f"/api/v1/goals/{goal['id']}/progress/", {"value": "100"}, format="json")
    assert api_client.get("/api/v1/notifications/unread-count/").json()["count"] == 1
    items = api_client.get("/api/v1/notifications/?unread=true").json()["results"]
    assert items[0]["type"] == "GOAL_COMPLETED" and items[0]["link"] == f"/goals/{goal['id']}"
    assert other_client.post(f"/api/v1/notifications/{items[0]['id']}/read/").status_code == 404
    assert api_client.post(f"/api/v1/notifications/{items[0]['id']}/read/").json()["read_at"]
    assert api_client.post("/api/v1/notifications/read-all/").status_code == 200
    assert api_client.get("/api/v1/notifications/unread-count/").json()["count"] == 0


def test_purge(user):
    from apps.notifications.tasks import purge_old_notifications

    n = Notification.objects.create(user=user, type="X", message_key="x")
    Notification.objects.filter(id=n.id).update(created_at=now() - timedelta(days=91))
    assert purge_old_notifications() == 1
    assert datetime  # imported for clarity of the test module
