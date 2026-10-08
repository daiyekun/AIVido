from __future__ import annotations

import json
import logging
import re
import secrets
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterable, Iterator, Mapping

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.sampling import (
    Decision,
    ParentBased,
    StaticSampler,
    TraceIdRatioBased,
)
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, TraceState
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_TRACER: trace.Tracer | None = None
_FALLBACK_TRACE_ID: ContextVar[str] = ContextVar("ainew_trace_id", default="")
_INITIALIZED = False
_INSTRUMENTED = False

_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
_SPAN_LOGGER = logging.getLogger("ainew.span")


class JsonSpanExporter(SpanExporter):
    def export(self, spans: Iterable[Any]) -> SpanExportResult:
        for span in spans:
            start_ns = getattr(span, "start_time", None)
            end_ns = getattr(span, "end_time", None)
            duration_ms = round((end_ns - start_ns) / 1_000_000, 3) if start_ns and end_ns else None
            status_code = ""
            status = getattr(span, "status", None)
            if status is not None:
                status_code = getattr(status.status_code, "name", str(status.status_code))
            payload: dict[str, Any] = {
                "message": "otel_span",
                "span_name": span.name,
                "trace_id": format(span.context.trace_id, "032x") if span.context else "",
                "span_id": format(span.context.span_id, "016x") if span.context else "",
                "parent_span_id": format(span.parent.span_id, "016x") if span.parent else "",
                "duration_ms": duration_ms,
                "status_code": status_code,
            }
            for key, value in (span.attributes or {}).items():
                if key.startswith("http.request.") or key.startswith("http.response."):
                    continue
                if isinstance(value, (str, int, float, bool)):
                    payload[key] = value
            _SPAN_LOGGER.info(payload.pop("message"), extra=payload)
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def init_tracing(app: Any = None, service_name: str | None = None) -> None:
    global _TRACER, _INITIALIZED, _INSTRUMENTED

    from app.core.config import settings

    if _INITIALIZED:
        _attach_middleware(app)
        return

    resource = Resource.create(
        {
            SERVICE_NAME: service_name or settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.env,
        }
    )
    if settings.otel_sample_ratio < 1.0:
        sampler = ParentBased(TraceIdRatioBased(settings.otel_sample_ratio))
    else:
        sampler = StaticSampler(Decision.RECORD_AND_SAMPLE)
    provider = TracerProvider(resource=resource, sampler=sampler)

    exporter: SpanExporter
    if settings.otel_exporter == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        exporter = ConsoleSpanExporter()
    elif settings.otel_exporter == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=settings.otel_otlp_endpoint, insecure=True)
        except Exception:
            exporter = JsonSpanExporter()
    else:
        exporter = JsonSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _TRACER = trace.get_tracer(settings.app_name)
    _INITIALIZED = True

    if not _INSTRUMENTED:
        HTTPXClientInstrumentor().instrument()
        CeleryInstrumentor().instrument()
        _INSTRUMENTED = True

    _attach_middleware(app)


def _attach_middleware(app: Any) -> None:
    if app is None:
        return
    if getattr(app.state, "trace_middleware_attached", False):
        return
    from app.core.middleware import TraceMiddleware

    app.add_middleware(TraceMiddleware)
    app.state.trace_middleware_attached = True


def get_tracer() -> trace.Tracer:
    if _TRACER is not None:
        return _TRACER
    return trace.get_tracer("ainew")


def current_trace_id() -> str:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is not None and ctx.is_valid:
        return format(ctx.trace_id, "032x")
    return _FALLBACK_TRACE_ID.get("")


def current_span_id() -> str:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is not None and ctx.is_valid:
        return format(ctx.span_id, "016x")
    return ""


def set_fallback_trace_id(trace_id: str) -> None:
    _FALLBACK_TRACE_ID.set(trace_id)


@contextmanager
def start_span(
    name: str,
    attributes: Mapping[str, Any] | None = None,
    parent_context: Context | None = None,
) -> Iterator[trace.Span]:
    tracer = get_tracer()
    with tracer.start_as_current_span(name, context=parent_context) as span:
        for key, value in (attributes or {}).items():
            if value is not None:
                span.set_attribute(key, value)
        yield span


def extract_incoming_context(headers: Mapping[str, str]) -> Context:
    lowered = {str(k).lower(): v for k, v in headers.items()}
    traceparent = lowered.get("traceparent")
    if traceparent:
        return TraceContextTextMapPropagator().extract({"traceparent": traceparent})

    trace_id_raw = lowered.get("x-trace-id", "")
    if _HEX32.match(trace_id_raw):
        span_context = SpanContext(
            trace_id=int(trace_id_raw, 16),
            span_id=int(secrets.token_hex(8), 16),
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
            trace_state=TraceState(),
        )
        ctx = trace.set_span_in_context(NonRecordingSpan(span_context))
        _FALLBACK_TRACE_ID.set(trace_id_raw.lower())
        return ctx

    _FALLBACK_TRACE_ID.set("")
    return otel_context.get_current()


def attach_context(ctx: Context) -> Any:
    return otel_context.attach(ctx)


def detach_context(token: Any) -> None:
    otel_context.detach(token)


def now_ms() -> float:
    return round(time.time() * 1000, 3)


def span_attrs_to_json(attributes: Mapping[str, Any] | None) -> str:
    if not attributes:
        return "{}"
    return json.dumps(dict(attributes), ensure_ascii=False, default=str)
