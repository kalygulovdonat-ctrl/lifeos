from datetime import timedelta

import pytest

from common.models import AuditLog
from common.time import local_today

pytestmark = pytest.mark.django_db


def today():
    return local_today("Asia/Bishkek").isoformat()


def test_daily_reflection_flow(api_client, user):
    assert api_client.get(f"/api/v1/journal/by-date/{today()}/").status_code == 404
    res = api_client.post(
        "/api/v1/journal/",
        {"entry_type": "DAILY", "sections": {"happened": "Сдал лабу", "learned": "", "grateful": "Друзьям"}},
        format="json",
    )
    assert res.status_code == 201, res.json()
    entry = res.json()
    assert entry["template_key"] == "daily_v1"
    assert entry["sections"] == {"happened": "Сдал лабу", "grateful": "Друзьям"}  # empty fields dropped
    assert entry["is_sensitive"] is True and entry["ai_allowed"] is False
    assert api_client.get(f"/api/v1/journal/by-date/{today()}/").json()["id"] == entry["id"]

    dup = api_client.post("/api/v1/journal/", {"entry_type": "DAILY"}, format="json")
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "JOURNAL_DAILY_EXISTS"

    res = api_client.patch(
        f"/api/v1/journal/{entry['id']}/", {"sections": {"tomorrow": "Спорт"}}, format="json"
    )
    assert res.json()["sections"] == {"tomorrow": "Спорт"}

    # entry text never reaches the audit log (SDD §6.4)
    for row in AuditLog.objects.filter(entity_type="journal_entry"):
        assert "Сдал" not in str(row.changes) and "Спорт" not in str(row.changes)


@pytest.mark.parametrize(
    "payload",
    [
        {"entry_type": "DAILY", "sections": {"secret": "x"}},
        {"entry_type": "FREE", "sections": {"happened": "x"}},
        {"entry_type": "DAILY", "sections": {"happened": "x" * 10_001}},
    ],
)
def test_section_validation(api_client, payload):
    assert api_client.post("/api/v1/journal/", payload, format="json").status_code == 400


def test_future_date_rejected(api_client):
    tomorrow = (local_today("Asia/Bishkek") + timedelta(days=1)).isoformat()
    res = api_client.post("/api/v1/journal/", {"entry_date": tomorrow, "body": "x"}, format="json")
    assert res.status_code == 400


def test_free_entries_search_and_delete(api_client):
    a = api_client.post(
        "/api/v1/journal/", {"title": "Идеи", "body": "Бот для расписания"}, format="json"
    ).json()
    api_client.post("/api/v1/journal/", {"title": "Мысли", "body": "Про отдых"}, format="json")
    found = api_client.get("/api/v1/journal/?q=расписания").json()["results"]
    assert [e["id"] for e in found] == [a["id"]]
    assert api_client.get("/api/v1/journal/?type=FREE").json()["count"] == 2
    assert api_client.delete(f"/api/v1/journal/{a['id']}/").status_code == 204
    assert api_client.get("/api/v1/journal/").json()["count"] == 1
    templates = api_client.get("/api/v1/journal/templates/").json()["results"]
    assert templates[0]["sections"][0] == "happened"


def test_isolation(api_client, other_client):
    e = api_client.post("/api/v1/journal/", {"body": "личное"}, format="json").json()
    for method in ("get", "patch", "delete"):
        assert (
            getattr(other_client, method)(f"/api/v1/journal/{e['id']}/", {}, format="json").status_code == 404
        )
    assert other_client.get("/api/v1/journal/").json()["count"] == 0
    assert other_client.get(f"/api/v1/journal/by-date/{today()}/").status_code == 404
