"""Read-side access. Every function takes the owner first (BR-002)."""

from django.db.models import QuerySet

from apps.accounts.models import Category, Tag, User, UserProfile


def profile_get(user: User) -> UserProfile:
    return UserProfile.objects.select_related("user").get(user=user)


def category_list(user: User, *, include_archived: bool = False) -> QuerySet[Category]:
    qs = Category.objects.filter(user=user)
    if not include_archived:
        qs = qs.filter(is_archived=False)
    return qs


def tag_list(user: User) -> QuerySet[Tag]:
    return Tag.objects.filter(user=user)
