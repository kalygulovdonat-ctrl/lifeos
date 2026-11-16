"""Domain exceptions and the single API error format (PRD §7.4, SDD §7.4)."""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exc
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger("lifeos.errors")


class LifeOSError(Exception):
    """Base domain error. Services raise these; the handler renders them."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"
    message = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class DomainValidationError(LifeOSError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "VALIDATION_ERROR"
    message = "The provided data is invalid."


class NotFoundError(LifeOSError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "Resource not found."


class ConflictError(LifeOSError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    message = "The request conflicts with the current state."


class UnprocessableError(LifeOSError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "UNPROCESSABLE"
    message = "The request is semantically invalid."


class ForbiddenError(LifeOSError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action."


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": False, "error": {"code": code, "message": message, "details": details or {}}}


def _normalize_details(detail: Any) -> dict[str, Any]:
    if isinstance(detail, dict):
        return {k: _as_list(v) for k, v in detail.items()}
    if isinstance(detail, list):
        return {"non_field_errors": [str(d) for d in detail]}
    return {}


def _as_list(value: Any) -> Any:
    if isinstance(value, list):
        return [_as_list(v) if isinstance(v, dict | list) else str(v) for v in value]
    if isinstance(value, dict):
        return {k: _as_list(v) for k, v in value.items()}
    return [str(value)]


_DRF_MAP: list[tuple[type[Exception], int, str, str]] = [
    (InvalidToken, 401, "TOKEN_EXPIRED", "Access token is invalid or expired."),
    (TokenError, 401, "TOKEN_EXPIRED", "Token is invalid or expired."),
    (drf_exc.NotAuthenticated, 401, "NOT_AUTHENTICATED", "Authentication credentials were not provided."),
    (drf_exc.AuthenticationFailed, 401, "NOT_AUTHENTICATED", "Authentication failed."),
    (
        drf_exc.PermissionDenied,
        403,
        "PERMISSION_DENIED",
        "You do not have permission to perform this action.",
    ),
    (drf_exc.NotFound, 404, "NOT_FOUND", "Resource not found."),
    (drf_exc.MethodNotAllowed, 405, "METHOD_NOT_ALLOWED", "Method not allowed."),
    (drf_exc.NotAcceptable, 406, "NOT_ACCEPTABLE", "Not acceptable."),
    (drf_exc.UnsupportedMediaType, 415, "UNSUPPORTED_MEDIA_TYPE", "Unsupported media type."),
    (drf_exc.Throttled, 429, "RATE_LIMITED", "Too many requests."),
    (drf_exc.ParseError, 400, "VALIDATION_ERROR", "Malformed request body."),
]


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    if isinstance(exc, LifeOSError):
        return Response(error_payload(exc.code, exc.message, exc.details), status=exc.status_code)

    if isinstance(exc, Http404):
        exc = drf_exc.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf_exc.PermissionDenied()

    if isinstance(exc, drf_exc.ValidationError):
        return Response(
            error_payload(
                "VALIDATION_ERROR", "The provided data is invalid.", _normalize_details(exc.detail)
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )

    for exc_type, http_status, code, message in _DRF_MAP:
        if isinstance(exc, exc_type):
            response = drf_exception_handler(exc, context)
            headers = {}
            if response is not None and "Retry-After" in response:
                headers["Retry-After"] = response["Retry-After"]
            if isinstance(exc, drf_exc.Throttled) and exc.wait:
                headers["Retry-After"] = str(int(exc.wait))
            return Response(error_payload(code, message), status=http_status, headers=headers)

    if isinstance(exc, drf_exc.APIException):
        return Response(error_payload(str(exc.default_code).upper(), str(exc.detail)), status=exc.status_code)

    request = context.get("request")
    logger.exception(
        "unhandled_exception",
        extra={"path": getattr(request, "path", None)},
        exc_info=exc,
    )
    return Response(
        error_payload("INTERNAL_ERROR", "Internal server error."),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
