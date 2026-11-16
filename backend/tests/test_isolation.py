"""User data isolation (BR-001, BR-002, PRD §12: "user A cannot read user B's data").

Every owner-scoped endpoint must answer 404 for another user's object id, and lists must
never contain foreign rows. Add each new module's endpoints to OWNED_ENDPOINTS.
"""

import pytest

from apps.accounts.models import Category, Tag

OWNED_ENDPOINTS = [
    ("/api/v1/categories/", lambda user: Category.objects.filter(user=user).first()),
    ("/api/v1/tags/", lambda user: Tag.objects.create(user=user, name="secret-tag")),
]


@pytest.mark.django_db
@pytest.mark.parametrize("base,factory", OWNED_ENDPOINTS, ids=[e[0] for e in OWNED_ENDPOINTS])
class TestIsolation:
    def test_foreign_object_is_not_found(self, base, factory, user, other_client):
        obj = factory(user)
        url = f"{base}{obj.id}/"
        for method in ("get", "patch", "delete"):
            res = getattr(other_client, method)(url, {}, format="json")
            assert res.status_code == 404, f"{method.upper()} {url} -> {res.status_code}"
            assert res.json()["error"]["code"] == "NOT_FOUND"
        assert type(obj).objects.filter(id=obj.id).exists()

    def test_list_excludes_foreign_rows(self, base, factory, user, other_client):
        obj = factory(user)
        ids = {row["id"] for row in other_client.get(base).json()["results"]}
        assert str(obj.id) not in ids

    def test_anonymous_is_rejected(self, base, factory, anon_client):
        assert anon_client.get(base).status_code == 401


@pytest.mark.django_db
def test_cannot_create_row_for_another_user(api_client, user, other_user):
    res = api_client.post("/api/v1/tags/", {"name": "x", "user": str(other_user.id)})
    assert res.status_code == 201
    assert Tag.objects.get(id=res.json()["id"]).user_id == user.id
