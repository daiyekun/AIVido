from __future__ import annotations

from typing import Any


class BizError(Exception):
    code: int = 99999
    http_status: int = 400

    def __init__(self, msg: str = "", code: int | None = None, http_status: int | None = None):
        self.msg = msg or "business error"
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        super().__init__(self.msg)

    def to_payload(self) -> dict[str, Any]:
        return {"code": self.code, "msg": self.msg, "data": None}


class UnauthorizedError(BizError):
    code = 10001
    http_status = 401

    def __init__(self, msg: str = "未登录或登录状态失效"):
        super().__init__(msg)


class TokenExpiredError(UnauthorizedError):
    code = 10002

    def __init__(self, msg: str = "登录凭证已过期"):
        super().__init__(msg)


class ForbiddenError(BizError):
    code = 10003
    http_status = 403

    def __init__(self, msg: str = "无权限访问"):
        super().__init__(msg)


class ParamError(BizError):
    code = 20001
    http_status = 400

    def __init__(self, msg: str = "参数非法"):
        super().__init__(msg)


class SmsCodeError(BizError):
    code = 10004
    http_status = 400

    def __init__(self, msg: str = "验证码错误或已过期"):
        super().__init__(msg)


class PhoneRegisteredError(BizError):
    code = 10005
    http_status = 400

    def __init__(self, msg: str = "手机号已注册"):
        super().__init__(msg)


class PhoneNotRegisteredError(BizError):
    code = 10006
    http_status = 400

    def __init__(self, msg: str = "手机号未注册"):
        super().__init__(msg)


class FileTypeNotSupportedError(ParamError):
    code = 20002

    def __init__(self, msg: str = "文件类型不支持"):
        super().__init__(msg)


class FileTooLargeError(ParamError):
    code = 20003

    def __init__(self, msg: str = "文件大小超出限制"):
        super().__init__(msg)


class ModelNotFoundError(BizError):
    code = 30001
    http_status = 400

    def __init__(self, msg: str = "模型不存在"):
        super().__init__(msg)


class ModelDisabledError(BizError):
    code = 30002
    http_status = 400

    def __init__(self, msg: str = "模型已禁用"):
        super().__init__(msg)


class CapabilityUnsupportedError(BizError):
    code = 30003
    http_status = 400

    def __init__(self, msg: str = "模型不支持该能力"):
        super().__init__(msg)


class TierOutOfRangeError(BizError):
    code = 30004
    http_status = 400

    def __init__(self, msg: str = "参数超出模型支持档位"):
        super().__init__(msg)


class PromptNotFoundError(BizError):
    code = 30005
    http_status = 400

    def __init__(self, msg: str = "提示词模板不存在"):
        super().__init__(msg)


class TaskNotFoundError(BizError):
    code = 40001
    http_status = 400

    def __init__(self, msg: str = "任务不存在"):
        super().__init__(msg)


class TaskStatusIllegalError(BizError):
    code = 40002
    http_status = 400

    def __init__(self, msg: str = "任务状态不允许该操作"):
        super().__init__(msg)


class QueueSubmitFailedError(BizError):
    code = 40003
    http_status = 503

    def __init__(self, msg: str = "队列提交失败"):
        super().__init__(msg)


class ModelCallFailedError(BizError):
    code = 50001
    http_status = 502

    def __init__(self, msg: str = "模型调用失败"):
        super().__init__(msg)


class ModelTimeoutError(BizError):
    code = 50002
    http_status = 504

    def __init__(self, msg: str = "模型调用超时"):
        super().__init__(msg)


class StorageWriteFailedError(BizError):
    code = 50003
    http_status = 500

    def __init__(self, msg: str = "对象存储写入失败"):
        super().__init__(msg)


class SensitiveWordError(BizError):
    code = 60001
    http_status = 400

    def __init__(self, msg: str = "提示词命中敏感词"):
        super().__init__(msg)


class InternalError(BizError):
    code = 99999
    http_status = 500

    def __init__(self, msg: str = "服务内部错误"):
        super().__init__(msg)


def register_exception_handlers(app: Any) -> None:
    import logging

    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from app.core.response import build_response
    from app.core.tracing import current_trace_id

    logger = logging.getLogger("ainew.api")

    async def biz_error_handler(_: Any, exc: BizError) -> JSONResponse:
        if exc.http_status >= 500:
            logger.error("biz_error", extra={"error_code": str(exc.code), "error_msg": exc.msg})
        return JSONResponse(
            status_code=exc.http_status,
            content=build_response(code=exc.code, msg=exc.msg, data=None),
        )

    async def validation_error_handler(_: Any, exc: RequestValidationError) -> JSONResponse:
        detail = []
        for err in exc.errors():
            detail.append(
                {
                    "loc": [str(item) for item in err.get("loc", [])],
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
            )
        return JSONResponse(
            status_code=400,
            content=build_response(code=20001, msg="参数校验失败", data={"detail": detail}),
        )

    async def http_error_handler(_: Any, exc: HTTPException) -> JSONResponse:
        code_map = {401: 10001, 403: 10003}
        code = code_map.get(exc.status_code, 40000 + exc.status_code)
        detail = exc.detail if isinstance(exc.detail, str) else "request error"
        return JSONResponse(
            status_code=exc.status_code,
            content=build_response(code=code, msg=detail, data=None),
        )

    async def unhandled_error_handler(_: Any, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", extra={"trace_id": current_trace_id()})
        return JSONResponse(
            status_code=500,
            content=build_response(code=99999, msg="服务内部错误", data=None),
        )

    app.add_exception_handler(BizError, biz_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
