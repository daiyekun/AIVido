from __future__ import annotations

from typing import Any


def current_trace_id() -> str:
    from app.core import tracing

    return tracing.current_trace_id()


def build_response(code: int, msg: str, data: Any = None, trace_id: str | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "msg": msg,
        "trace_id": trace_id if trace_id is not None else current_trace_id(),
        "data": data,
    }


def ok(data: Any = None, msg: str = "success") -> dict[str, Any]:
    return build_response(code=0, msg=msg, data=data)


def ok_page(items: list[Any], total: int, page: int, size: int, msg: str = "success") -> dict[str, Any]:
    return build_response(
        code=0,
        msg=msg,
        data={"items": items, "total": total, "page": page, "size": size},
    )


def fail(code: int, msg: str) -> dict[str, Any]:
    return build_response(code=code, msg=msg, data=None)
