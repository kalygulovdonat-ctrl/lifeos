from django.urls import path

from apps.journal import views

urlpatterns = [
    path("journal/", views.JournalListView.as_view(), name="journal"),
    path("journal/templates/", views.JournalTemplatesView.as_view(), name="journal-templates"),
    path("journal/by-date/<str:day>/", views.JournalByDateView.as_view(), name="journal-by-date"),
    path("journal/<uuid:entry_id>/", views.JournalDetailView.as_view(), name="journal-detail"),
]
