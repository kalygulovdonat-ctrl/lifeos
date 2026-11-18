"""Shared view helpers: owner-scoped viewsets, health checks, JSON 404/500."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import error_payload


class OwnedModelViewSet(viewsets.ModelViewSet):
    """Every query starts from a selector filtered by request.user (BR-002, anti-IDOR).

    A foreign object is simply absent from the queryset, so it yields 404, not 403.
    Subclasses set `queryset = Model.objects.none()` (used only for schema generation),
    implement `selector(user)`, and route writes through services.
    """

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def selector(self, user: Any) -> QuerySet:  # pragma: no cover - abstract
        raise NotImplementedError

    def get_queryset(self) -> QuerySet:
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return self.selector(self.request.user)


class HealthLiveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(responses={200: dict})
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class HealthReadyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(responses={200: dict, 503: dict})
    def get(self, request: Request) -> Response:
        checks = {"database": _check_db(), "cache": _check_cache()}
        ok = all(checks.values())
        return Response(
            {
                "status": "ok" if ok else "unavailable",
                "checks": {k: "ok" if v else "fail" for k, v in checks.items()},
            },
            status=200 if ok else 503,
        )


def _check_db() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def _check_cache() -> bool:
    try:
        cache.set("health:ping", "1", timeout=5)
        return cache.get("health:ping") == "1"
    except Exception:
        return False


def json_404(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse(error_payload("NOT_FOUND", "Resource not found."), status=404)


def json_500(request: HttpRequest) -> JsonResponse:
    return JsonResponse(error_payload("INTERNAL_ERROR", "Internal server error."), status=500)


def spa_index(request: HttpRequest) -> HttpResponse:
    """index.html of the React build for client-side routes (used only when FRONTEND_DIST is set)."""
    page = Path(settings.FRONTEND_DIST, "index.html").read_bytes()
    response = HttpResponse(page, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response
