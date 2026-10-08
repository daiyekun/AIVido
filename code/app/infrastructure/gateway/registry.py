from __future__ import annotations

from typing import Callable, Type

from app.infrastructure.gateway.base import BaseModelAdapter
from app.infrastructure.gateway.errors import AdapterNotRegisteredError

ADAPTER_REGISTRY: dict[str, Type[BaseModelAdapter]] = {}


def register_adapter(key: str) -> Callable[[Type[BaseModelAdapter]], Type[BaseModelAdapter]]:
    def decorator(cls: Type[BaseModelAdapter]) -> Type[BaseModelAdapter]:
        ADAPTER_REGISTRY[key] = cls
        return cls

    return decorator


def get_adapter_class(key: str) -> Type[BaseModelAdapter]:
    if key not in ADAPTER_REGISTRY:
        raise AdapterNotRegisteredError(f"适配器未注册: {key}")
    return ADAPTER_REGISTRY[key]


def resolve_adapter(key: str, model_conf: dict) -> BaseModelAdapter:
    return get_adapter_class(key)(model_conf)
