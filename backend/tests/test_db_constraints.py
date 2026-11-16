"""DB-level invariants that must hold even if a service is bypassed (SDD §4.1).

Name uniqueness uses an app-computed name_key, so it holds on SQLite and on PostgreSQL
with any LC_CTYPE (LOWER() does not fold Cyrillic under the C locale).
"""

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import Category, Tag, UserProfile


@pytest.mark.django_db
def test_category_name_unique_case_insensitive_cyrillic(user):
    Category.objects.create(user=user, scope="TASK", name="Университет", color="#112233")
    with pytest.raises(IntegrityError), transaction.atomic():
        Category.objects.create(user=user, scope="TASK", name="УНИВЕРСИТЕТ", color="#112233")


@pytest.mark.django_db
def test_tag_name_unique_case_insensitive_cyrillic(user):
    Tag.objects.create(user=user, name="Учёба")
    with pytest.raises(IntegrityError), transaction.atomic():
        Tag.objects.create(user=user, name="учёба")


@pytest.mark.django_db
def test_archived_category_frees_the_name(user):
    first = Category.objects.create(user=user, scope="TASK", name="Old", color="#112233")
    first.is_archived = True
    first.save()
    Category.objects.create(user=user, scope="TASK", name="old", color="#112233")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [("week_start", 0), ("language", "kg"), ("theme", "neon"), ("time_format", "36h")],
)
def test_profile_check_constraints(user, field, value):
    with pytest.raises(IntegrityError), transaction.atomic():
        UserProfile.objects.filter(user=user).update(**{field: value})


@pytest.mark.django_db
def test_profile_day_window_constraint(user):
    with pytest.raises(IntegrityError), transaction.atomic():
        UserProfile.objects.filter(user=user).update(day_start_time="22:00", day_end_time="06:00")


@pytest.mark.django_db
def test_category_color_constraint(user):
    with pytest.raises(IntegrityError), transaction.atomic():
        Category.objects.create(user=user, scope="ANY", name="Bad", color="red")


@pytest.mark.django_db
def test_bulk_create_without_name_key_fails_loudly(user):
    with pytest.raises(IntegrityError), transaction.atomic():
        Tag.objects.bulk_create([Tag(user=user, name="bypass")])
