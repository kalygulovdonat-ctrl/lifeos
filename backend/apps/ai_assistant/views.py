"""AI assistant API (SDD §7.2)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai_assistant import services
from apps.ai_assistant.models import AIAction, AIContextAccess, AIConversation, AIMessage, Scope
from common.exceptions import NotFoundError


def _get(model: Any, user: Any, pk: str) -> Any:
    try:
        return model.objects.get(user=user, id=pk)
    except (model.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIAction
        fields = [
            "id",
            "action_type",
            "payload",
            "edited_payload",
            "assumptions",
            "preview",
            "status",
            "result_object_type",
            "result_object_id",
            "error",
            "expires_at",
            "decided_at",
            "executed_at",
        ]


class MessageSerializer(serializers.ModelSerializer):
    actions = ActionSerializer(many=True, read_only=True)

    class Meta:
        model = AIMessage
        fields = ["id", "role", "content", "status", "error_code", "created_at", "actions"]


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIConversation
        fields = ["id", "title", "model", "created_at", "updated_at"]


class StatusView(APIView):
    """Whether AI is configured and what the user allowed (drives the settings card)."""

    @extend_schema(responses={200: dict})
    def get(self, request: Request) -> Response:
        return Response(
            {
                "enabled": settings.AI_ENABLED,
                "provider": settings.AI_PROVIDER,
                "model": settings.AI_MODEL if settings.AI_PROVIDER != "fake" else "demo",
                "scopes": sorted(services.active_scopes(request.user)),
                "all_scopes": Scope.values,
                "tokens_this_month": services.tokens_this_month(request.user),
                "monthly_limit": settings.AI_MONTHLY_TOKEN_LIMIT,
            }
        )


class ConsentSerializer(serializers.Serializer):
    scopes = serializers.ListField(child=serializers.ChoiceField(choices=Scope.choices), max_length=10)


class ConsentView(APIView):
    @extend_schema(request=ConsentSerializer, responses={200: dict})
    def put(self, request: Request) -> Response:
        s = ConsentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        scopes = services.set_consents(user=request.user, scopes=s.validated_data["scopes"])
        return Response({"scopes": sorted(scopes)})


class ConversationListView(APIView):
    @extend_schema(responses={200: ConversationSerializer(many=True)}, operation_id="ai_conversations_list")
    def get(self, request: Request) -> Response:
        items = AIConversation.objects.filter(user=request.user, is_archived=False)[:50]
        return Response({"results": ConversationSerializer(items, many=True).data})

    @extend_schema(request=None, responses={201: ConversationSerializer})
    def post(self, request: Request) -> Response:
        convo = services.conversation_create(user=request.user, title=str(request.data.get("title", "")))
        return Response(ConversationSerializer(convo).data, status=status.HTTP_201_CREATED)


class ConversationDetailView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request: Request, conversation_id: str) -> Response:
        services.expire_stale(request.user)
        convo = _get(AIConversation, request.user, conversation_id)
        msgs = convo.messages.prefetch_related("actions")
        return Response(
            {**ConversationSerializer(convo).data, "messages": MessageSerializer(msgs, many=True).data}
        )

    @extend_schema(responses={204: None})
    def delete(self, request: Request, conversation_id: str) -> Response:
        # Cascades to messages, drafts and the context log; created objects stay (SDD §9.6).
        _get(AIConversation, request.user, conversation_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SendSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=4000)


class MessagesView(APIView):
    throttle_scope = "ai"

    @extend_schema(request=SendSerializer, responses={202: dict})
    def post(self, request: Request, conversation_id: str) -> Response:
        convo = _get(AIConversation, request.user, conversation_id)
        s = SendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        question, answer = services.send_message(
            user=request.user, conversation=convo, content=s.validated_data["content"]
        )
        return Response(
            {
                "user_message": MessageSerializer(question).data,
                "assistant_message": MessageSerializer(answer).data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class MessageDetailView(APIView):
    @extend_schema(responses={200: MessageSerializer})
    def get(self, request: Request, message_id: str) -> Response:
        msg = AIMessage.objects.filter(user=request.user, id=message_id).prefetch_related("actions").first()
        if msg is None:
            raise NotFoundError()
        return Response(MessageSerializer(msg).data)


class ContextView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request: Request, message_id: str) -> Response:
        msg = _get(AIMessage, request.user, message_id)
        rows = AIContextAccess.objects.filter(user=request.user, message=msg)
        return Response(
            {
                "results": [
                    {"scope": r.scope, "object_type": r.object_type, "count": len(r.object_ids)} for r in rows
                ]
            }
        )


class ActionListView(APIView):
    @extend_schema(responses={200: ActionSerializer(many=True)}, operation_id="ai_actions_list")
    def get(self, request: Request) -> Response:
        services.expire_stale(request.user)
        qs = AIAction.objects.filter(user=request.user)
        if wanted := request.query_params.get("status"):
            qs = qs.filter(status=wanted)
        return Response({"results": ActionSerializer(qs.order_by("-created_at")[:100], many=True).data})


class ConfirmSerializer(serializers.Serializer):
    edited_payload = serializers.DictField(required=False, allow_null=True)


class ConfirmView(APIView):
    @extend_schema(request=ConfirmSerializer, responses={200: ActionSerializer})
    def post(self, request: Request, action_id: str) -> Response:
        action = _get(AIAction, request.user, action_id)
        s = ConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        action = services.action_confirm(
            user=request.user, action=action, edited_payload=s.validated_data.get("edited_payload")
        )
        return Response(ActionSerializer(action).data)


class RejectView(APIView):
    @extend_schema(request=None, responses={200: ActionSerializer})
    def post(self, request: Request, action_id: str) -> Response:
        action = services.action_reject(user=request.user, action=_get(AIAction, request.user, action_id))
        return Response(ActionSerializer(action).data)


class RevertView(APIView):
    @extend_schema(request=None, responses={200: ActionSerializer})
    def post(self, request: Request, action_id: str) -> Response:
        action = services.action_revert(user=request.user, action=_get(AIAction, request.user, action_id))
        return Response(ActionSerializer(action).data)
