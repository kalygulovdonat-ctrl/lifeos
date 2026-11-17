from django.urls import path

from apps.tasks import views

urlpatterns = [
    path("tasks/", views.TaskListView.as_view(), name="tasks"),
    path("tasks/quick/", views.TaskQuickView.as_view(), name="tasks-quick"),
    path("tasks/<uuid:task_id>/", views.TaskDetailView.as_view(), name="task-detail"),
    path("tasks/<uuid:task_id>/status/", views.TaskStatusView.as_view(), name="task-status"),
    path("tasks/<uuid:task_id>/complete/", views.TaskCompleteView.as_view(), name="task-complete"),
    path("tasks/<uuid:task_id>/postpone/", views.TaskPostponeView.as_view(), name="task-postpone"),
    path("tasks/<uuid:task_id>/triage/", views.TaskTriageView.as_view(), name="task-triage"),
    path("tasks/<uuid:task_id>/archive/", views.TaskArchiveView.as_view(), name="task-archive"),
    path("tasks/<uuid:task_id>/restore/", views.TaskRestoreView.as_view(), name="task-restore"),
    path("tasks/<uuid:task_id>/history/", views.TaskHistoryView.as_view(), name="task-history"),
    path("tasks/<uuid:task_id>/schedule/", views.TaskScheduleView.as_view(), name="task-schedule"),
    path("tasks/<uuid:task_id>/subtasks/", views.SubtaskListView.as_view(), name="task-subtasks"),
    path(
        "tasks/<uuid:task_id>/subtasks/reorder/",
        views.SubtaskReorderView.as_view(),
        name="task-subtasks-reorder",
    ),
    path("subtasks/<uuid:subtask_id>/", views.SubtaskDetailView.as_view(), name="subtask-detail"),
]
