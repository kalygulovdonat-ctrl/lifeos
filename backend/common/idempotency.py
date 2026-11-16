"""Idempotency-Key support for POST endpoints (ADR-019, NFR-012).

Usage on a DRF view method::

    @idempotent
    def create(self, request, *args, **kwargs): ...

Flow: a placeholder row is inserted first, so a concurrent duplicate request with the
same key hits the unique constraint and gets 409 instead of executing twice.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import timedelta
from functools import wraps
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response

from common.exceptions import ConflictError, DomainValidationError, UnprocessableError
from common.models import IdempotencyRecord

HEADER = "Idempotency-Key"
TTL = timedelta(hours=24)
MAX_KEY_LENGTH = 64


def _request_hash(request: Request) -> str:
    raw = json.dumps(request.data, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(f"{request.method}:{request.path}:{raw}".encode()).hexdigest()


def idempotent(view_method: Callable[..., Response]) -> Callable[..., Response]:
    @wraps(view_method)
    def wrapper(self: Any, request: Request, *args: Any, **kwargs: Any) -> Response:
        key = request.headers.get(HEADER)
        if not key or not request.user.is_authenticated:
            return view_method(self, request, *args, **kwargs)
        if len(key) > MAX_KEY_LENGTH:
            raise DomainValidationError(details={HEADER: [f"Must be at most {MAX_KEY_LENGTH} characters."]})

        request_hash = _request_hash(request)
        record = _claim(request, key, request_hash)
        if record.response_status is not None:
            return Response(record.response_body, status=record.response_status)

        try:
            response = view_method(self, request, *args, **kwargs)
        except Exception:
            record.delete()
            raise

        if response.status_code >= 500:
            record.delete()
        else:
            record.response_status = response.status_code
            record.response_body = response.data
            record.save(update_fields=["response_status", "response_body"])
        return response

    return wrapper


def _claim(request: Request, key: str, request_hash: str) -> IdempotencyRecord:
    user = request.user
    IdempotencyRecord.objects.filter(user=user, key=key, created_at__lt=timezone.now() - TTL).delete()
    try:
        with transaction.atomic():
            return IdempotencyRecord.objects.create(
                user=user,
                key=key,
                method=request.method,
                path=request.path[:200],
                request_hash=request_hash,
            )
    except IntegrityError:
        existing = IdempotencyRecord.objects.get(user=user, key=key)

    if existing.request_hash != request_hash:
        raise UnprocessableError(
            "Idempotency-Key was already used with a different request.",
            code="IDEMPOTENCY_KEY_REUSED",
        )
    if existing.response_status is None:
        raise ConflictError("A request with this Idempotency-Key is in progress.", code="REQUEST_IN_PROGRESS")
    return existing
