"""JSON logging with request id and redaction of secrets (SDD §6.4)."""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from common.request_context import current_request_id

SENSITIVE_KEYS = {
    "password",
    "old_password",
    "new_password",
    "token",
    "access",
    "refresh",
    "authorization",
    "cookie",
    "secret",
    "api_key",
    "sections",
    "body",
    "content",
}
_INLINE_SECRET = re.compile(
    r"(?i)(password|token|authorization|api[_-]?key|secret)(['\"]?\s*[:=]\s*['\"]?)([^\s'\",}]+)"
)
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if str(k).lower() in SENSITIVE_KEYS else redact(v)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(redact(v) for v in value)
    if isinstance(value, str):
        return _INLINE_SECRET.sub(r"\1\2***", value)
    return value


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rid = current_request_id()
        record.request_id = str(rid) if rid else None
        return True


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            record.args = redact(record.args)
        for key in list(vars(record)):
            if key not in _STANDARD_ATTRS:
                if key.lower() in SENSITIVE_KEYS:
                    setattr(record, key, "***")
                else:
                    setattr(record, key, redact(getattr(record, key)))
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)
