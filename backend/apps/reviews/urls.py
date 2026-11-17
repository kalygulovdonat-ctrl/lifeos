from django.urls import path

from apps.reviews import views

urlpatterns = [
    path("reviews/", views.ReviewListView.as_view(), name="reviews"),
    path("reviews/<uuid:review_id>/", views.ReviewDetailView.as_view(), name="review-detail"),
    path("reviews/<uuid:review_id>/refresh-stats/", views.RefreshView.as_view(), name="review-refresh"),
    path(
        "reviews/<uuid:review_id>/unfinished-tasks/", views.UnfinishedView.as_view(), name="review-unfinished"
    ),
    path("reviews/<uuid:review_id>/task-decisions/", views.DecisionsView.as_view(), name="review-decisions"),
    path("reviews/<uuid:review_id>/complete/", views.CompleteView.as_view(), name="review-complete"),
]
