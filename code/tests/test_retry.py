from __future__ import annotations

from app.infrastructure.gateway.errors import (
    AdapterNotSupportedError,
    ModelCallHttpError,
    ModelCallTimeoutError,
    error_code_of,
)
from app.infrastructure.mq.topology import retry_tier


def test_retry_tier_mapping():
    assert retry_tier(1) == "30s"
    assert retry_tier(2) == "2m"
    assert retry_tier(3) == "10m"
    assert retry_tier(10) == "10m"


def test_error_code_of():
    assert error_code_of(ModelCallTimeoutError("t")) == "50002"
    assert error_code_of(ModelCallHttpError("x", 500)) == "50001"
    assert error_code_of(AdapterNotSupportedError("v")) == "30003"
    assert error_code_of(ValueError("v")) == "50001"
