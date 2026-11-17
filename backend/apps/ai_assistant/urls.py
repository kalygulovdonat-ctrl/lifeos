from django.urls import path

from apps.ai_assistant import views

urlpatterns = [
    path("ai/status/", views.StatusView.as_view(), name="ai-status"),
    path("ai/consents/", views.ConsentView.as_view(), name="ai-consents"),
    path("ai/conversations/", views.ConversationListView.as_view(), name="ai-conversations"),
    path(
        "ai/conversations/<uuid:conversation_id>/",
        views.ConversationDetailView.as_view(),
        name="ai-conversation",
    ),
    path(
        "ai/conversations/<uuid:conversation_id>/messages/", views.MessagesView.as_view(), name="ai-messages"
    ),
    path("ai/messages/<uuid:message_id>/", views.MessageDetailView.as_view(), name="ai-message"),
    path("ai/messages/<uuid:message_id>/context/", views.ContextView.as_view(), name="ai-message-context"),
    path("ai/actions/", views.ActionListView.as_view(), name="ai-actions"),
    path("ai/actions/<uuid:action_id>/confirm/", views.ConfirmView.as_view(), name="ai-action-confirm"),
    path("ai/actions/<uuid:action_id>/reject/", views.RejectView.as_view(), name="ai-action-reject"),
    path("ai/actions/<uuid:action_id>/revert/", views.RevertView.as_view(), name="ai-action-revert"),
]
