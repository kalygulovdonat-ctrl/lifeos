from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import Category, Tag, User, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "is_active", "is_staff", "date_joined")
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "email_verified_at",
                    "deletion_requested_at",
                )
            },
        ),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "timezone", "language")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "scope", "user", "is_archived")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "user")
