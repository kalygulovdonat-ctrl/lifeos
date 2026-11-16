"""Refresh-token cookie handling and CSRF enforcement for cookie endpoints (ADR-004)."""

from __future__ import annotations

from django.conf import settings
from django.middleware.csrf import get_token
from rest_framework.authentication import CSRFCheck
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from common.exceptions import ForbiddenError


def issue_tokens(user: User) -> tuple[str, str]:
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def set_refresh_cookie(response: Response, refresh: str) -> None:
    cfg = settings.REFRESH_COOKIE
    response.set_cookie(
        cfg["name"],
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=cfg["path"],
        secure=cfg["secure"],
        httponly=True,
        samesite=cfg["samesite"],
    )


def clear_refresh_cookie(response: Response) -> None:
    cfg = settings.REFRESH_COOKIE
    response.delete_cookie(cfg["name"], path=cfg["path"], samesite=cfg["samesite"])


def read_refresh_cookie(request: Request) -> str | None:
    return request.COOKIES.get(settings.REFRESH_COOKIE["name"])


def ensure_csrf_cookie(request: Request) -> None:
    """Make Django set the csrftoken cookie on this response (double-submit pattern)."""
    get_token(request._request)


def enforce_csrf(request: Request) -> None:
    """Same check DRF's SessionAuthentication performs, applied to cookie-authenticated endpoints."""
    check = CSRFCheck(lambda req: None)
    check.process_request(request._request)
    reason = check.process_view(request._request, None, (), {})
    if reason:
        raise ForbiddenError("CSRF verification failed.", code="CSRF_FAILED")
