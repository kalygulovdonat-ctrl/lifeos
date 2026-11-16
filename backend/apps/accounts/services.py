"""Write-side business operations for identity and reference data."""

from __future__ import annotations

from datetime import time
from typing import Any

from django.conf import settings
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import Category, CategoryScope, Tag, User, UserProfile, name_key
from common.audit import audit, diff
from common.exceptions import ConflictError, DomainValidationError, ForbiddenError
from common.time import is_valid_timezone, now

# (system_key, default English name, color). Names are translated in the UI by system_key.
DEFAULT_CATEGORIES: list[tuple[str, str, str]] = [
    ("work", "Work", "#3B82F6"),
    ("study", "Study", "#8B5CF6"),
    ("health", "Health", "#10B981"),
    ("sport", "Sport", "#F97316"),
    ("personal", "Personal", "#EC4899"),
    ("rest", "Rest", "#14B8A6"),
    ("household", "Household", "#A16207"),
    ("social", "Social", "#EAB308"),
]


def _validate_timezone(tz: str) -> None:
    if not is_valid_timezone(tz):
        raise DomainValidationError(details={"timezone": ["Unknown time zone."]})


@transaction.atomic
def user_register(
    *,
    email: str,
    password: str,
    display_name: str,
    timezone: str = "UTC",
    language: str = "ru",
) -> User:
    if not settings.REGISTRATION_OPEN:
        raise ForbiddenError("Registration is closed.", code="REGISTRATION_CLOSED")
    _validate_timezone(timezone)
    email = email.strip().lower()
    if User.objects.filter(email=email).exists():
        raise ConflictError("An account with this email already exists.", code="EMAIL_TAKEN")

    candidate = User(email=email)
    try:
        password_validation.validate_password(password, user=candidate)
    except DjangoValidationError as exc:
        raise DomainValidationError(details={"password": list(exc.messages)}) from exc

    try:
        user = User.objects.create_user(email=email, password=password)
    except IntegrityError as exc:  # concurrent registration with the same email
        raise ConflictError("An account with this email already exists.", code="EMAIL_TAKEN") from exc

    UserProfile.objects.create(
        user=user, display_name=display_name.strip(), timezone=timezone, language=language
    )
    Category.objects.bulk_create(
        Category(
            user=user,
            scope=CategoryScope.ANY,
            name=name,
            name_key=name_key(name),  # bulk_create bypasses Model.save()
            system_key=key,
            color=color,
            sort_order=i,
        )
        for i, (key, name, color) in enumerate(DEFAULT_CATEGORIES)
    )
    audit(user=user, entity_type="user", entity_id=user.id, action="REGISTER")
    return user


PROFILE_FIELDS = {
    "display_name",
    "timezone",
    "language",
    "time_format",
    "date_format",
    "week_start",
    "theme",
    "day_start_time",
    "day_end_time",
    "pomodoro_settings",
    "overload_threshold_minutes",
}


@transaction.atomic
def profile_update(*, user: User, data: dict[str, Any]) -> UserProfile:
    profile = UserProfile.objects.select_for_update().get(user=user)
    data = {k: v for k, v in data.items() if k in PROFILE_FIELDS}
    if "timezone" in data:
        _validate_timezone(data["timezone"])

    start = data.get("day_start_time", profile.day_start_time)
    end = data.get("day_end_time", profile.day_end_time)
    if _as_time(end) <= _as_time(start):
        raise DomainValidationError(details={"day_end_time": ["Day end must be later than day start."]})

    changes = diff(profile, data)
    for field, value in data.items():
        setattr(profile, field, value)
    profile.save()
    if changes:
        audit(user=user, entity_type="user_profile", entity_id=user.id, action="UPDATE", changes=changes)
    return profile


def _as_time(value: Any) -> Any:
    if isinstance(value, str):
        return time.fromisoformat(value)
    return value


@transaction.atomic
def onboarding_complete(*, user: User) -> UserProfile:
    profile = UserProfile.objects.select_for_update().get(user=user)
    if profile.onboarding_completed_at is None:
        profile.onboarding_completed_at = now()
        profile.save(update_fields=["onboarding_completed_at", "updated_at"])
    return profile


@transaction.atomic
def password_change(*, user: User, old_password: str, new_password: str) -> None:
    if not user.check_password(old_password):
        raise DomainValidationError(details={"old_password": ["Current password is incorrect."]})
    try:
        password_validation.validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise DomainValidationError(details={"new_password": list(exc.messages)}) from exc
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    revoke_all_refresh_tokens(user=user)
    audit(user=user, entity_type="user", entity_id=user.id, action="PASSWORD_CHANGE")


def revoke_all_refresh_tokens(*, user: User) -> None:
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


# --- Categories --------------------------------------------------------------------


def _name_conflict(field: str = "name") -> DomainValidationError:
    return DomainValidationError(details={field: ["An item with this name already exists."]})


def _ensure_unique_name(qs: Any, name: str, exclude_id: Any = None) -> None:
    """Friendly 400 before hitting the DB; the unique index on name_key is the race-safe guarantee."""
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    if qs.filter(name_key=name_key(name)).exists():
        raise _name_conflict()


def category_create(*, user: User, **data: Any) -> Category:
    _ensure_unique_name(
        Category.objects.filter(user=user, scope=data.get("scope", CategoryScope.ANY), is_archived=False),
        data["name"],
    )
    try:
        with transaction.atomic():
            category = Category.objects.create(user=user, **data)
    except IntegrityError as exc:
        raise _name_conflict() from exc
    audit(user=user, entity_type="category", entity_id=category.id, action="CREATE")
    return category


def category_update(*, user: User, category: Category, data: dict[str, Any]) -> Category:
    if "name" in data and category.system_key and data["name"] != category.name:
        data["is_name_custom"] = True
    if "name" in data:
        _ensure_unique_name(
            Category.objects.filter(user=user, scope=category.scope, is_archived=False),
            data["name"],
            exclude_id=category.id,
        )
    changes = diff(category, data)
    for field, value in data.items():
        setattr(category, field, value)
    try:
        with transaction.atomic():
            category.save()
    except IntegrityError as exc:
        raise _name_conflict() from exc
    if changes:
        audit(user=user, entity_type="category", entity_id=category.id, action="UPDATE", changes=changes)
    return category


def category_archive(*, user: User, category: Category) -> None:
    """Archiving keeps history intact (BR-004): linked records keep their category."""
    category.is_archived = True
    category.save(update_fields=["is_archived", "updated_at"])
    audit(user=user, entity_type="category", entity_id=category.id, action="ARCHIVE")


# --- Tags ----------------------------------------------------------------------------


def tag_create(*, user: User, **data: Any) -> Tag:
    _ensure_unique_name(Tag.objects.filter(user=user), data["name"])
    try:
        with transaction.atomic():
            tag = Tag.objects.create(user=user, **data)
    except IntegrityError as exc:
        raise _name_conflict() from exc
    return tag


def tag_update(*, user: User, tag: Tag, data: dict[str, Any]) -> Tag:
    if "name" in data:
        _ensure_unique_name(Tag.objects.filter(user=user), data["name"], exclude_id=tag.id)
    for field, value in data.items():
        setattr(tag, field, value)
    try:
        with transaction.atomic():
            tag.save()
    except IntegrityError as exc:
        raise _name_conflict() from exc
    return tag


def tag_delete(*, user: User, tag: Tag) -> None:
    tag.delete()
