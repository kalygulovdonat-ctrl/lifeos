"""UUID v7 generator (ADR-002). Python 3.14+ has it built in; older versions use `uuid6`."""

import uuid

try:
    _uuid7 = uuid.uuid7  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - Python < 3.14
    from uuid6 import uuid7 as _uuid7_pkg

    def _uuid7() -> uuid.UUID:
        return uuid.UUID(str(_uuid7_pkg()))


def uuid7() -> uuid.UUID:
    return _uuid7()
