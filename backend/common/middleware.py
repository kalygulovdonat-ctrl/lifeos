import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from common.request_context import request_id_var


class RequestIdMiddleware:
    """Accepts a valid X-Request-ID or generates one; echoes it in the response."""

    header = "X-Request-ID"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        raw = request.headers.get(self.header, "")
        try:
            request_id = uuid.UUID(raw)
        except ValueError:
            request_id = uuid.uuid4()
        request.request_id = request_id  # type: ignore[attr-defined]
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[self.header] = str(request_id)
        return response
