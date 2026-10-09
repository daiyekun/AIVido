from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.gateway.errors import (
    AdapterNotRegisteredError,
    AdapterNotSupportedError,
    is_retryable,
)
from app.infrastructure.gateway.registry import get_adapter_class, resolve_adapter


def test_stub_adapter_registered():
    adapter = resolve_adapter("stub", {})
    assert adapter.supports("txt2img") is True
    assert adapter.supports("img2img") is True
    assert adapter.supports("txt2vid") is False
    assert adapter.supports("vid2vid") is False


def test_stub_adapter_dispatch():
    adapter = resolve_adapter("stub", {})
    result = asyncio.run(adapter.txt2img({}, "trace-123"))
    assert result.provider_task_id == "stub-txt2img"


def test_unsupported_method_raises():
    adapter = resolve_adapter("stub", {})
    with pytest.raises(AdapterNotSupportedError):
        asyncio.run(adapter.vid2vid({}, "trace-123"))


def test_unknown_adapter_raises():
    with pytest.raises(AdapterNotRegisteredError):
        get_adapter_class("nope")


def test_is_retryable():
    from app.infrastructure.gateway.errors import ModelCallHttpError, ModelCallTimeoutError

    assert is_retryable(ModelCallTimeoutError("timeout")) is True
    assert is_retryable(ModelCallHttpError("x", status_code=429)) is True
    assert is_retryable(ModelCallHttpError("x", status_code=400)) is False
    assert is_retryable(ConnectionError("conn")) is True
    assert is_retryable(ValueError("v")) is False
