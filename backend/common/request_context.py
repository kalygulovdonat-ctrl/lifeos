"""Per-request context (request id) shared by logging and audit."""

from contextvars import ContextVar
from uuid import UUID

request_id_var: ContextVar[UUID | None] = ContextVar("request_id", default=None)


def current_request_id() -> UUID | None:
    return request_id_var.get()
