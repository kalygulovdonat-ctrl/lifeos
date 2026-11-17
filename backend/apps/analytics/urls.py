from django.urls import path

from apps.analytics import views

urlpatterns = [
    path("analytics/daily/", views.DailyView.as_view(), name="analytics-daily"),
    path("analytics/weekly/", views.WeeklyView.as_view(), name="analytics-weekly"),
    path("analytics/monthly/", views.MonthlyView.as_view(), name="analytics-monthly"),
]
