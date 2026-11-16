from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.models import Category, Language, Tag, UserProfile
from common.time import is_valid_timezone


def validate_tz(value: str) -> str:
    if not is_valid_timezone(value):
        raise serializers.ValidationError("Unknown time zone.")
    return value


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    display_name = serializers.CharField(max_length=80)
    timezone = serializers.CharField(max_length=64, default="UTC", validators=[validate_tz])
    language = serializers.ChoiceField(choices=Language.choices, default=Language.RU)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)


class PomodoroSerializer(serializers.Serializer):
    work = serializers.IntegerField(min_value=1, max_value=180)
    short = serializers.IntegerField(min_value=1, max_value=60)
    long = serializers.IntegerField(min_value=1, max_value=120)
    cycle = serializers.IntegerField(min_value=1, max_value=12)


class ProfileSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    timezone = serializers.CharField(max_length=64, validators=[validate_tz], required=False)
    pomodoro_settings = PomodoroSerializer(required=False)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "email",
            "display_name",
            "avatar",
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
            "onboarding_completed_at",
        ]
        read_only_fields = ["avatar", "onboarding_completed_at"]


class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    profile = ProfileSerializer()


class AccessResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "scope",
            "name",
            "system_key",
            "is_name_custom",
            "color",
            "icon",
            "sort_order",
            "is_archived",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "system_key", "is_name_custom", "is_archived", "created_at", "updated_at"]
        # Uniqueness is enforced by the DB constraint and reported by the service.
        validators: list[Any] = []

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        if self.instance is not None and not isinstance(self.instance, list):
            fields["scope"].read_only = True  # scope is fixed after creation
        return fields


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        validators: list[Any] = []
