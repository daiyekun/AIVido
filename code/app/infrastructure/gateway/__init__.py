from __future__ import annotations

from app.infrastructure.gateway import adapters  # noqa: F401
from app.infrastructure.gateway.base import AdapterResult, BaseModelAdapter
from app.infrastructure.gateway.client import GatewayClient, gateway_client
from app.infrastructure.gateway.errors import (
    AdapterNotRegisteredError,
    AdapterNotSupportedError,
    GatewayError,
    ModelCallHttpError,
    ModelCallTimeoutError,
    ModelCallTransportError,
    is_retryable,
)
from app.infrastructure.gateway.registry import (
    ADAPTER_REGISTRY,
    get_adapter_class,
    register_adapter,
    resolve_adapter,
)

__all__ = [
    "ADAPTER_REGISTRY",
    "AdapterNotRegisteredError",
    "AdapterNotSupportedError",
    "AdapterResult",
    "BaseModelAdapter",
    "GatewayClient",
    "GatewayError",
    "ModelCallHttpError",
    "ModelCallTimeoutError",
    "ModelCallTransportError",
    "gateway_client",
    "get_adapter_class",
    "is_retryable",
    "register_adapter",
    "resolve_adapter",
]
