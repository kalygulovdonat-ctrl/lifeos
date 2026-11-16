import pytest

from apps.accounts.models import Category, Tag
from common.models import AuditLog


@pytest.mark.django_db
class TestProfile:
    def test_get(self, api_client, user):
        res = api_client.get("/api/v1/profile/")
        assert res.status_code == 200
        body = res.json()
        assert body["id"] == str(user.id)
        assert body["week_start"] == 1
        assert body["time_format"] == "24h"
        assert body["pomodoro_settings"] == {"work": 25, "short": 5, "long": 15, "cycle": 4}

    def test_requires_auth(self, anon_client):
        res = anon_client.get("/api/v1/profile/")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "NOT_AUTHENTICATED"

    def test_patch_and_audit(self, api_client, user):
        res = api_client.patch(
            "/api/v1/profile/",
            {"language": "en", "time_format": "12h", "timezone": "Europe/Berlin", "week_start": 7},
        )
        assert res.status_code == 200, res.json()
        body = res.json()
        assert (body["language"], body["time_format"], body["timezone"], body["week_start"]) == (
            "en",
            "12h",
            "Europe/Berlin",
            7,
        )
        log = AuditLog.objects.get(user=user, entity_type="user_profile")
        assert log.changes["language"] == ["ru", "en"]

    def test_email_is_read_only(self, api_client, user):
        api_client.patch("/api/v1/profile/", {"email": "hacker@example.com"})
        user.refresh_from_db()
        assert user.email == "owner@example.com"

    @pytest.mark.parametrize(
        "payload,field",
        [
            ({"timezone": "Nowhere/City"}, "timezone"),
            ({"week_start": 8}, "week_start"),
            ({"language": "de"}, "language"),
            ({"day_start_time": "22:00", "day_end_time": "06:00"}, "day_end_time"),
            ({"pomodoro_settings": {"work": 0, "short": 5, "long": 15, "cycle": 4}}, "pomodoro_settings"),
        ],
    )
    def test_validation(self, api_client, payload, field):
        res = api_client.patch("/api/v1/profile/", payload, format="json")
        assert res.status_code == 400
        assert field in res.json()["error"]["details"]

    def test_onboarding_complete(self, api_client):
        res = api_client.post("/api/v1/profile/onboarding/complete/")
        assert res.status_code == 200
        assert res.json()["onboarding_completed_at"]


@pytest.mark.django_db
class TestCategories:
    def test_list_defaults(self, api_client):
        res = api_client.get("/api/v1/categories/")
        assert res.status_code == 200
        keys = {c["system_key"] for c in res.json()["results"]}
        assert {"work", "study", "rest"} <= keys

    def test_create_and_duplicate_name(self, api_client):
        payload = {"name": "Университет", "color": "#112233", "scope": "TASK"}
        assert api_client.post("/api/v1/categories/", payload).status_code == 201
        dup = api_client.post("/api/v1/categories/", {**payload, "name": "университет"})
        assert dup.status_code == 400
        assert "name" in dup.json()["error"]["details"]

    def test_same_name_different_scope_ok(self, api_client):
        assert (
            api_client.post(
                "/api/v1/categories/", {"name": "X", "color": "#112233", "scope": "TASK"}
            ).status_code
            == 201
        )
        assert (
            api_client.post(
                "/api/v1/categories/", {"name": "X", "color": "#112233", "scope": "HABIT"}
            ).status_code
            == 201
        )

    def test_bad_color(self, api_client):
        res = api_client.post("/api/v1/categories/", {"name": "Y", "color": "red"})
        assert res.status_code == 400
        assert "color" in res.json()["error"]["details"]

    def test_rename_system_category_marks_custom(self, api_client, user):
        cat = Category.objects.get(user=user, system_key="work")
        res = api_client.patch(f"/api/v1/categories/{cat.id}/", {"name": "Job"})
        assert res.status_code == 200
        assert res.json()["is_name_custom"] is True
        assert res.json()["system_key"] == "work"

    def test_delete_archives(self, api_client, user):
        cat = Category.objects.get(user=user, system_key="sport")
        assert api_client.delete(f"/api/v1/categories/{cat.id}/").status_code == 204
        cat.refresh_from_db()
        assert cat.is_archived
        listed = {c["id"] for c in api_client.get("/api/v1/categories/").json()["results"]}
        assert str(cat.id) not in listed
        archived = api_client.get("/api/v1/categories/?include_archived=true").json()["results"]
        assert str(cat.id) in {c["id"] for c in archived}

    def test_put_not_allowed(self, api_client, user):
        cat = Category.objects.filter(user=user).first()
        res = api_client.put(f"/api/v1/categories/{cat.id}/", {"name": "Z", "color": "#000000"})
        assert res.status_code == 405
        assert res.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


@pytest.mark.django_db
class TestTags:
    def test_crud(self, api_client):
        res = api_client.post("/api/v1/tags/", {"name": "python"})
        assert res.status_code == 201
        tag_id = res.json()["id"]
        assert api_client.post("/api/v1/tags/", {"name": "Python"}).status_code == 400
        assert api_client.patch(f"/api/v1/tags/{tag_id}/", {"color": "#ABCDEF"}).json()["color"] == "#ABCDEF"
        assert api_client.delete(f"/api/v1/tags/{tag_id}/").status_code == 204
        assert not Tag.objects.filter(id=tag_id).exists()
