from django.urls import path

from apps.goals import views

urlpatterns = [
    path("goals/", views.GoalListView.as_view(), name="goals"),
    path("goals/<uuid:goal_id>/", views.GoalDetailView.as_view(), name="goal-detail"),
    path("goals/<uuid:goal_id>/status/", views.GoalStatusView.as_view(), name="goal-status"),
    path("goals/<uuid:goal_id>/progress/", views.GoalProgressView.as_view(), name="goal-progress"),
    path("goals/<uuid:goal_id>/progress-history/", views.GoalHistoryView.as_view(), name="goal-history"),
    path("goals/<uuid:goal_id>/tasks/", views.GoalTasksView.as_view(), name="goal-tasks"),
    path(
        "goals/<uuid:goal_id>/tasks/<uuid:task_id>/", views.GoalTaskLinkView.as_view(), name="goal-task-link"
    ),
    path("goals/<uuid:goal_id>/milestones/", views.MilestoneListView.as_view(), name="goal-milestones"),
    path("milestones/<uuid:milestone_id>/", views.MilestoneDetailView.as_view(), name="milestone-detail"),
    path(
        "milestones/<uuid:milestone_id>/complete/",
        views.MilestoneCompleteView.as_view(),
        name="milestone-complete",
    ),
]
