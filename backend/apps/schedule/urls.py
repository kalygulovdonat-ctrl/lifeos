from django.urls import path

from apps.schedule import views

urlpatterns = [
    path("events/", views.EventListView.as_view(), name="events"),
    path("events/conflicts/", views.ConflictsView.as_view(), name="events-conflicts"),
    path("events/check-conflicts/", views.CheckConflictsView.as_view(), name="events-check-conflicts"),
    path("events/<uuid:event_id>/", views.EventDetailView.as_view(), name="event-detail"),
    path("events/<uuid:event_id>/reschedule/", views.EventRescheduleView.as_view(), name="event-reschedule"),
    path("events/<uuid:event_id>/status/", views.EventStatusView.as_view(), name="event-status"),
    path("event-series/<uuid:series_id>/", views.SeriesDetailView.as_view(), name="series-detail"),
    path(
        "event-series/<uuid:series_id>/occurrences/<int:epoch>/",
        views.OccurrenceView.as_view(),
        name="series-occurrence",
    ),
    path("schedule/free-slots/", views.FreeSlotsView.as_view(), name="free-slots"),
]
