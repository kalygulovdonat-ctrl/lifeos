from django.contrib import admin

from apps.schedule.models import Event, EventReschedule, EventSeries, EventSeriesExdate


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "start_at", "end_at", "time_type", "status"]
    list_filter = ["time_type", "status"]
    search_fields = ["title"]
    raw_id_fields = ["user", "category", "task", "series"]


@admin.register(EventSeries)
class EventSeriesAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "rrule", "dtstart_at", "is_active"]
    raw_id_fields = ["user", "category", "task"]


admin.site.register(EventSeriesExdate)
admin.site.register(EventReschedule)
