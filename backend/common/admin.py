from django.contrib import admin

from common.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_type", "entity_type", "action", "user")
    list_filter = ("actor_type", "entity_type", "action")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):  # append-only
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
