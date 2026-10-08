from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.tracing import current_span_id, current_trace_id

_SERVICE = "ainew"
_CONFIGURED = False

_EXTRA_FIELDS = (
    "service",
    "trace_id",
    "span_id",
    "task_id",
    "session_id",
    "msg_id",
    "user_id",
    "model_id",
    "adapter_key",
    "system_prompt_id",
    "prompt_id",
    "duration_ms",
    "error_code",
    "error_msg",
    "status_code",
    "http_method",
    "path",
    "client_ip",
    "queue",
    "routing_key",
    "retry_count",
    "resolved_task_type",
    "matched_scope",
    "prompt_sha8",
    "expect_credit",
    "bucket",
    "object_key",
    "size_bytes",
    "provider_task_id",
    "span_name",
    "parent_span_id",
    "result",
    "count",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        created = datetime.fromtimestamp(record.created, tz=timezone.utc)
        payload: dict = {
            "timestamp": created.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z",
            "level": record.levelname,
            "service": getattr(record, "service", None) or _SERVICE,
            "trace_id": getattr(record, "trace_id", None) or current_trace_id(),
            "span_id": getattr(record, "span_id", None) or current_span_id(),
            "message": record.getMessage(),
        }
        for key in _EXTRA_FIELDS:
            if key in ("service", "trace_id", "span_id"):
                continue
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(service_name: str | None = None) -> None:
    global _CONFIGURED, _SERVICE

    from app.core.config import settings

    _SERVICE = service_name or settings.service_name
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
        uv_logger.setLevel(level)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)
    _CONFIGURED = True


def is_configured() -> bool:
    return _CONFIGURED
