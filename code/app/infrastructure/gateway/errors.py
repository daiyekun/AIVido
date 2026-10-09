from __future__ import annotations

RETRYABLE_HTTP_CODES = frozenset({429, 500, 502, 503, 504})


class GatewayError(Exception):
    retryable: bool = False

    def __init__(self, message: str = "", *, retryable: bool | None = None):
        super().__init__(message)
        self.message = message
        if retryable is not None:
            self.retryable = retryable


class AdapterNotRegisteredError(GatewayError):
    retryable = False


class AdapterNotSupportedError(GatewayError):
    retryable = False


class ModelCallTimeoutError(GatewayError):
    retryable = True


class ModelCallTransportError(GatewayError):
    retryable = True


class ModelCallHttpError(GatewayError):
    def __init__(self, message: str, status_code: int, *, retryable: bool | None = None):
        if retryable is None:
            retryable = status_code in RETRYABLE_HTTP_CODES
        super().__init__(message, retryable=retryable)
        self.status_code = status_code


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, GatewayError):
        return exc.retryable
    return isinstance(exc, (TimeoutError, ConnectionError, OSError))


def error_code_of(exc: BaseException) -> str:
    if isinstance(exc, ModelCallTimeoutError):
        return "50002"
    if isinstance(exc, (AdapterNotRegisteredError, AdapterNotSupportedError)):
        return "30003"
    if isinstance(exc, (ModelCallHttpError, ModelCallTransportError)):
        return "50001"
    return "50001"
