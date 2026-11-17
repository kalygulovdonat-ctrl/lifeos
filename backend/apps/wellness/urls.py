from django.urls import path

from apps.wellness import views

urlpatterns = [
    path("wellness/checkins/", views.CheckinListView.as_view(), name="wellness-checkins"),
    path("wellness/checkins/<uuid:checkin_id>/", views.CheckinDetailView.as_view(), name="wellness-checkin"),
    path("wellness/sleep/", views.SleepListView.as_view(), name="wellness-sleep"),
    path("wellness/sleep/<uuid:sleep_id>/", views.SleepDetailView.as_view(), name="wellness-sleep-detail"),
    path("wellness/summary/", views.SummaryView.as_view(), name="wellness-summary"),
]
