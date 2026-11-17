"""Identity and reference data (SDD §4.2, §4.3)."""

from __future__ import annotations

from datetime import time
from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

from common.ids import uuid7
from common.models import OwnedModel, choices_check

HEX_COLOR = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Color must be a #RRGGBB hex value.")


def name_key(value: str) -> str:
    """Case- and whitespace-insensitive key for uniqueness checks.

    Computed in Python (str.casefold) so uniqueness does not depend on the database
    locale: PostgreSQL LOWER() leaves Cyrillic unchanged under LC_CTYPE=C, SQLite LOWER()
    is ASCII-only.
    """
    return " ".join(value.split()).casefold()


def default_pomodoro() -> dict[str, int]:
    return {"work": 25, "short": 5, "long": 15, "cycle": 4}


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra: Any) -> User:
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra["is_staff"] = True
        extra["is_superuser"] = True
        user = self._create(email, password, **extra)
        UserProfile.objects.get_or_create(user=user, defaults={"display_name": user.email.split("@")[0]})
        return user


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "app_user"  # "user" is a reserved word in PostgreSQL
        constraints = [models.UniqueConstraint(Lower("email"), name="app_user_email_lower_uq")]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email


class Language(models.TextChoices):
    RU = "ru", "Русский"
    EN = "en", "English"
    KY = "ky", "Кыргызча"


class TimeFormat(models.TextChoices):
    H12 = "12h"
    H24 = "24h"


class Theme(models.TextChoices):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class UserProfile(models.Model):
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=80)
    avatar = models.CharField(max_length=255, blank=True, null=True)
    timezone = models.CharField(max_length=64, default="UTC")
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.RU)
    time_format = models.CharField(max_length=3, choices=TimeFormat.choices, default=TimeFormat.H24)
    date_format = models.CharField(max_length=16, default="DD.MM.YYYY")
    week_start = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(7)]
    )
    theme = models.CharField(max_length=8, choices=Theme.choices, default=Theme.SYSTEM)
    day_start_time = models.TimeField(default=time(7, 0))
    day_end_time = models.TimeField(default=time(23, 0))
    pomodoro_settings = models.JSONField(default=default_pomodoro)
    overload_threshold_minutes = models.PositiveIntegerField(default=600)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profile"
        constraints = [
            choices_check("language", Language, "user_profile_language_ck"),
            choices_check("time_format", TimeFormat, "user_profile_time_format_ck"),
            choices_check("theme", Theme, "user_profile_theme_ck"),
            models.CheckConstraint(
                condition=Q(week_start__gte=1, week_start__lte=7), name="user_profile_week_start_ck"
            ),
            models.CheckConstraint(
                condition=Q(day_end_time__gt=F("day_start_time")), name="user_profile_day_window_ck"
            ),
        ]

    def __str__(self) -> str:
        return self.display_name


class CategoryScope(models.TextChoices):
    TASK = "TASK"
    EVENT = "EVENT"
    HABIT = "HABIT"
    GOAL = "GOAL"
    JOURNAL = "JOURNAL"
    TIME = "TIME"
    ANY = "ANY"


class Category(OwnedModel):
    scope = models.CharField(max_length=10, choices=CategoryScope.choices, default=CategoryScope.ANY)
    name = models.CharField(max_length=60)
    name_key = models.CharField(max_length=120, editable=False, default="")
    system_key = models.CharField(max_length=40, null=True, blank=True)
    is_name_custom = models.BooleanField(default=False)
    color = models.CharField(max_length=7, validators=[HEX_COLOR])
    icon = models.CharField(max_length=40, null=True, blank=True)
    sort_order = models.IntegerField(default=0)
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = "category"
        ordering = ["sort_order", "name"]
        constraints = [
            choices_check("scope", CategoryScope, "category_scope_ck"),
            models.CheckConstraint(condition=Q(color__regex=r"^#[0-9A-Fa-f]{6}$"), name="category_color_ck"),
            models.UniqueConstraint(
                fields=["user", "scope", "name_key"],
                condition=Q(is_archived=False),
                name="category_user_scope_name_uq",
            ),
            # Fails loudly if a write path bypasses save() (bulk_create / update()).
            models.CheckConstraint(condition=~Q(name_key=""), name="category_name_key_set_ck"),
        ]
        indexes = [models.Index(fields=["user", "scope"], name="category_user_scope_ix")]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.name_key = name_key(self.name)
        if (fields := kwargs.get("update_fields")) is not None and "name" in fields:
            kwargs["update_fields"] = {*fields, "name_key"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Tag(OwnedModel):
    name = models.CharField(max_length=40)
    name_key = models.CharField(max_length=80, editable=False, default="")
    color = models.CharField(max_length=7, validators=[HEX_COLOR], null=True, blank=True)

    class Meta:
        db_table = "tag"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name_key"], name="tag_user_name_uq"),
            models.CheckConstraint(condition=~Q(name_key=""), name="tag_name_key_set_ck"),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.name_key = name_key(self.name)
        if (fields := kwargs.get("update_fields")) is not None and "name" in fields:
            kwargs["update_fields"] = {*fields, "name_key"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
