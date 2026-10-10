import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Set per request by RequestContextMiddleware; None outside a request.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Extra attributes that call sites may attach with `extra=...`. Anything else is dropped,
# so accidental fields (for example request bodies) are never written to logs.
_ALLOWED_EXTRA_FIELDS = ("method", "path", "status_code", "duration_ms", "error_code")


class JsonFormatter(logging.Formatter):
    """Formats each record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # An explicit request_id on the record wins: error handlers run outside the contextvar scope.
        request_id = getattr(record, "request_id", None) or request_id_ctx.get()
        if request_id is not None:
            payload["request_id"] = request_id
        for field in _ALLOWED_EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    """Replaces root logging handlers with a single JSON stream handler on stdout.

    Call once at process start (the application factory does this).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
