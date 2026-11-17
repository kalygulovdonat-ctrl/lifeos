from django.urls import path

from apps.time_tracking import views

urlpatterns = [
    path("timer/", views.TimerView.as_view(), name="timer"),
    path("timer/start/", views.TimerStartView.as_view(), name="timer-start"),
    path("timer/pause/", views.TimerPauseView.as_view(), name="timer-pause"),
    path("timer/resume/", views.TimerResumeView.as_view(), name="timer-resume"),
    path("timer/stop/", views.TimerStopView.as_view(), name="timer-stop"),
    path("timer/discard/", views.TimerDiscardView.as_view(), name="timer-discard"),
    path("time-entries/", views.TimeEntryListView.as_view(), name="time-entries"),
    path("time-entries/plan-vs-actual/", views.PlanVsActualView.as_view(), name="time-plan-vs-actual"),
    path("time-entries/<uuid:entry_id>/", views.TimeEntryDetailView.as_view(), name="time-entry-detail"),
]
