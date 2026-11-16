from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import user_register

PASSWORD = "Str0ng-Passw0rd!"


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(email: str | None = None, **kwargs) -> User:
        counter["n"] += 1
        return user_register(
            email=email or f"user{counter['n']}@example.com",
            password=PASSWORD,
            display_name=kwargs.pop("display_name", f"User {counter['n']}"),
            timezone=kwargs.pop("timezone", "Asia/Bishkek"),
            language=kwargs.pop("language", "ru"),
        )

    return _make


@pytest.fixture
def user(make_user) -> User:
    return make_user("owner@example.com")


@pytest.fixture
def other_user(make_user) -> User:
    return make_user("intruder@example.com")


@pytest.fixture
def anon_client() -> APIClient:
    return APIClient()


@pytest.fixture
def api_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def other_client(other_user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client
