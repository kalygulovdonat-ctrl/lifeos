from django.contrib import admin

from apps.tasks.models import Subtask, Task, TaskStatusChange


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "status", "priority", "due_at", "created_at"]
    list_filter = ["status", "priority"]
    search_fields = ["title"]
    raw_id_fields = ["user", "category"]


admin.site.register(Subtask)
admin.site.register(TaskStatusChange)
