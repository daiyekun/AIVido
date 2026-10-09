from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.tracing import start_span
from app.infrastructure.gateway.errors import (
    ModelCallHttpError,
    ModelCallTimeoutError,
    ModelCallTransportError,
)

logger = logging.getLogger("ainew.gateway")

_CAPABILITY_TIMEOUT: dict[str, int] = {
    "image": settings.model_call_timeout_image,
    "video": settings.model_call_timeout_video,
    "chat": settings.model_call_timeout_chat,
}


class GatewayClient:
    """统一 HTTP 客户端：超时 / 传输层重试 / OTel 埋点集中于本层实现。"""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def request(
        self,
        method: str,
        url: str,
        *,
        capability: str = "image",
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        effective_timeout = timeout or float(_CAPABILITY_TIMEOUT.get(capability, 120))
        client = await self._get_client()
        retries = max(0, settings.model_transport_retries)
        last_exc: httpx.ConnectError | None = None

        with start_span(
            "model_call_http",
            {"http.url": str(url), "http.method": method.upper(), "capability": capability},
        ):
            for attempt in range(retries + 1):
                try:
                    resp = await client.request(
                        method,
                        url,
                        headers=headers,
                        json=json,
                        params=params,
                        timeout=effective_timeout,
                    )
                except httpx.ConnectError as exc:
                    last_exc = exc
                    if attempt < retries:
                        logger.warning(
                            "gateway_connect_retry",
                            extra={"url": str(url), "attempt": attempt + 1},
                        )
                        continue
                    raise ModelCallTransportError(str(exc)) from exc
                except httpx.TimeoutException as exc:
                    raise ModelCallTimeoutError(str(exc)) from exc
                except httpx.TransportError as exc:
                    raise ModelCallTransportError(str(exc)) from exc

                if resp.status_code >= 400:
                    detail = ""
                    try:
                        body = resp.json()
                        code = body.get("code") or ""
                        message = body.get("message") or ""
                        if code or message:
                            detail = f" | {code} {message}".strip()
                    except Exception:  # noqa: BLE001
                        pass
                    raise ModelCallHttpError(
                        f"model http error {resp.status_code}{detail}",
                        status_code=resp.status_code,
                    )
                return resp

            raise ModelCallTransportError(str(last_exc) if last_exc else "connection failed")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


gateway_client = GatewayClient()
