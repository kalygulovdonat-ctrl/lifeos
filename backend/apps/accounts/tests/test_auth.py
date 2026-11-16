import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Category, User
from common.models import AuditLog
from conftest import PASSWORD

COOKIE = settings.REFRESH_COOKIE["name"]


def register(client, **overrides):
    payload = {
        "email": "New.User@Example.com",
        "password": PASSWORD,
        "display_name": "Нурсултан",
        "timezone": "Asia/Bishkek",
        "language": "ky",
    }
    payload.update(overrides)
    return client.post("/api/v1/auth/register/", payload, format="json")


@pytest.mark.django_db
class TestRegister:
    def test_creates_user_profile_and_default_categories(self, anon_client):
        res = register(anon_client)
        assert res.status_code == 201
        body = res.json()
        assert body["access"]
        assert body["profile"]["email"] == "new.user@example.com"
        assert body["profile"]["language"] == "ky"
        assert body["profile"]["timezone"] == "Asia/Bishkek"

        user = User.objects.get(email="new.user@example.com")
        assert Category.objects.filter(user=user, system_key="rest").exists()
        assert AuditLog.objects.filter(user=user, action="REGISTER").exists()

    def test_sets_httponly_refresh_cookie(self, anon_client):
        res = register(anon_client)
        cookie = res.cookies[COOKIE]
        assert cookie.value
        assert cookie["httponly"]
        assert cookie["path"] == "/api/v1/auth/"
        assert cookie["samesite"] == "Lax"
        assert "refresh" not in res.json()

    def test_duplicate_email_case_insensitive(self, anon_client):
        assert register(anon_client).status_code == 201
        res = register(APIClient(), email="NEW.user@example.COM")
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "EMAIL_TAKEN"

    def test_weak_password_rejected(self, anon_client):
        res = register(anon_client, password="12345")
        assert res.status_code == 400
        body = res.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "password" in body["error"]["details"]

    def test_unknown_timezone_rejected(self, anon_client):
        res = register(anon_client, timezone="Mars/Olympus")
        assert res.status_code == 400
        assert "timezone" in res.json()["error"]["details"]

    def test_kg_is_not_a_language_code(self, anon_client):
        res = register(anon_client, language="kg")
        assert res.status_code == 400

    @override_settings(REGISTRATION_OPEN=False)
    def test_registration_closed(self, anon_client):
        res = register(anon_client)
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "REGISTRATION_CLOSED"


@pytest.mark.django_db
class TestLoginRefreshLogout:
    def login(self, client, user):
        return client.post("/api/v1/auth/login/", {"email": user.email.upper(), "password": PASSWORD})

    def test_login_returns_access_and_cookie(self, anon_client, user):
        res = self.login(anon_client, user)
        assert res.status_code == 200
        assert res.json()["access"]
        assert res.cookies[COOKIE].value

    def test_wrong_password(self, anon_client, user):
        res = anon_client.post("/api/v1/auth/login/", {"email": user.email, "password": "nope-nope-nope"})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_access_token_authenticates(self, anon_client, user):
        access = self.login(anon_client, user).json()["access"]
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        assert client.get("/api/v1/profile/").status_code == 200

    def test_invalid_access_token(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
        res = client.get("/api/v1/profile/")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "TOKEN_EXPIRED"

    def test_refresh_rotates_and_old_token_is_blacklisted(self, anon_client, user):
        self.login(anon_client, user)
        old = anon_client.cookies[COOKIE].value

        res = anon_client.post("/api/v1/auth/refresh/")
        assert res.status_code == 200
        assert res.json()["access"]
        new = res.cookies[COOKIE].value
        assert new and new != old

        replay = APIClient()
        replay.cookies[COOKIE] = old
        res = replay.post("/api/v1/auth/refresh/")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "REFRESH_INVALID"

    def test_refresh_without_cookie(self, anon_client):
        res = anon_client.post("/api/v1/auth/refresh/")
        assert res.status_code == 401

    def test_refresh_requires_csrf(self, user):
        client = APIClient(enforce_csrf_checks=True)
        self.login(client, user)
        assert client.post("/api/v1/auth/refresh/").json()["error"]["code"] == "CSRF_FAILED"

        csrf = client.cookies["csrftoken"].value
        res = client.post("/api/v1/auth/refresh/", HTTP_X_CSRFTOKEN=csrf)
        assert res.status_code == 200

    def test_logout_blacklists_refresh(self, anon_client, user):
        self.login(anon_client, user)
        token = anon_client.cookies[COOKIE].value
        res = anon_client.post("/api/v1/auth/logout/")
        assert res.status_code == 204
        assert res.cookies[COOKIE].value == ""

        replay = APIClient()
        replay.cookies[COOKIE] = token
        assert replay.post("/api/v1/auth/refresh/").status_code == 401

    def test_password_change_revokes_other_sessions(self, anon_client, user):
        self.login(anon_client, user)
        other_device = anon_client.cookies[COOKIE].value

        client = APIClient()
        client.force_authenticate(user=user)
        res = client.post(
            "/api/v1/auth/password/change/",
            {"old_password": PASSWORD, "new_password": "An0ther-Str0ng-Pass"},
        )
        assert res.status_code == 200
        assert res.json()["access"]

        replay = APIClient()
        replay.cookies[COOKIE] = other_device
        assert replay.post("/api/v1/auth/refresh/").status_code == 401
        assert (
            anon_client.post(
                "/api/v1/auth/login/", {"email": user.email, "password": "An0ther-Str0ng-Pass"}
            ).status_code
            == 200
        )

    def test_password_change_wrong_old(self, api_client):
        res = api_client.post(
            "/api/v1/auth/password/change/",
            {"old_password": "wrong-password", "new_password": "An0ther-Str0ng-Pass"},
        )
        assert res.status_code == 400
        assert "old_password" in res.json()["error"]["details"]

    def test_inactive_user_cannot_login(self, anon_client, user):
        user.is_active = False
        user.save()
        assert self.login(anon_client, user).status_code == 401
