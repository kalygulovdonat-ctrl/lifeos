"""Notifications API (SDD §7.2)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications import services
from apps.notifications.models import Notification
from common.exceptions import NotFoundError
from common.pagination import PageNumberPagination


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "type", "message_key", "params", "link", "read_at", "created_at"]


class ListQuery(serializers.Serializer):
    unread = serializers.BooleanField(required=False, default=False)


class NotificationListView(APIView):
    @extend_schema(
        parameters=[ListQuery],
        responses={200: NotificationSerializer(many=True)},
        operation_id="notifications_list",
    )
    def get(self, request: Request) -> Response:
        q = ListQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        qs = Notification.objects.filter(user=request.user)
        if q.validated_data["unread"]:
            qs = qs.filter(read_at__isnull=True)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(NotificationSerializer(page, many=True).data)


class UnreadCountView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request: Request) -> Response:
        return Response(
            {"count": Notification.objects.filter(user=request.user, read_at__isnull=True).count()}
        )


class ReadView(APIView):
    @extend_schema(request=None, responses={200: NotificationSerializer})
    def post(self, request: Request, notification_id: str) -> Response:
        try:
            item = Notification.objects.get(user=request.user, id=notification_id)
        except Notification.DoesNotExist as exc:
            raise NotFoundError() from exc
        return Response(NotificationSerializer(services.mark_read(user=request.user, notification=item)).data)


class ReadAllView(APIView):
    @extend_schema(request=None, responses={200: dict})
    def post(self, request: Request) -> Response:
        return Response({"updated": services.mark_all_read(user=request.user)}, status=status.HTTP_200_OK)
