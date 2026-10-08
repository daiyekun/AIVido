from __future__ import annotations

import logging
import time

from opentelemetry.trace import Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core import tracing

logger = logging.getLogger("ainew.http")


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = tracing.extract_incoming_context(request.headers)
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else ""
        started = time.perf_counter()
        status_code = 500

        with tracing.start_span(
            f"HTTP {method} {path}",
            attributes={
                "http.request.method": method,
                "url.path": path,
                "url.scheme": request.url.scheme,
                "client.address": client_ip,
            },
            parent_context=incoming,
        ) as span:
            try:
                response = await call_next(request)
                status_code = response.status_code
                span.set_attribute("http.response.status_code", status_code)
                trace_id = tracing.current_trace_id()
                response.headers["X-Trace-Id"] = trace_id
                return response
            except BaseException as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                raise
            finally:
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                span.set_attribute("server.request.duration_ms", duration_ms)
                user_id = getattr(request.state, "user_id", None)
                logger.info(
                    "http_request",
                    extra={
                        "http_method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "client_ip": client_ip,
                        "user_id": user_id,
                        "trace_id": tracing.current_trace_id(),
                        "span_id": tracing.current_span_id(),
                    },
                )
