from django.urls import path

from apps.habits import views

urlpatterns = [
    path("habits/", views.HabitListView.as_view(), name="habits"),
    path("habits/today/", views.HabitTodayView.as_view(), name="habits-today"),
    path("habits/<uuid:habit_id>/", views.HabitDetailView.as_view(), name="habit-detail"),
    path("habits/<uuid:habit_id>/archive/", views.HabitArchiveView.as_view(), name="habit-archive"),
    path("habits/<uuid:habit_id>/restore/", views.HabitRestoreView.as_view(), name="habit-restore"),
    path("habits/<uuid:habit_id>/logs/", views.HabitLogsView.as_view(), name="habit-logs"),
    path("habits/<uuid:habit_id>/history/", views.HabitHistoryView.as_view(), name="habit-history"),
    path("habits/<uuid:habit_id>/stats/", views.HabitStatsView.as_view(), name="habit-stats"),
    path("habits/<uuid:habit_id>/pauses/", views.HabitPausesView.as_view(), name="habit-pauses"),
    path("habit-logs/<uuid:log_id>/", views.HabitLogDetailView.as_view(), name="habit-log-detail"),
    path("habit-pauses/<uuid:pause_id>/", views.HabitPauseDetailView.as_view(), name="habit-pause-detail"),
]
