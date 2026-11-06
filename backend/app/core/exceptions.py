"""统一错误模型与异常处理。

成功响应是 ``{data}``（列表端点另加 ``meta``）；失败响应统一为
``{code, message, details, requestId}``。业务代码只管抛 ``AppError``，
映射到 HTTP 状态码与错误体的工作全部集中在这里。
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("app.errors")


class AppError(Exception):
    """业务异常基类。

    ``code`` 是面向前端的稳定错误码（如 ``PROJECT_NOT_FOUND``），``message``
    是可直接展示的中文描述，``details`` 携带可选的结构化补充信息。
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def error_payload(request: Request, code: str, message: str, details: Any = None) -> dict[str, Any]:
    """构造统一错误体（requestId 与响应头 ``X-Request-ID`` 对得上）。"""
    return {
        "code": code,
        "message": message,
        "details": details,
        "requestId": getattr(request.state, "request_id", None),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """把 AppError 与请求参数校验错误接入 FastAPI 的异常处理链。"""
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        """AppError → 统一错误体（状态码取异常自带值）。"""
        # 业务异常:4xx 记 warning,5xx 记 error(不打堆栈,保持日志整洁)。
        log = logger.error if exc.status_code >= 500 else logger.warning
        log(
            "业务异常 %s %s -> %s %s: %s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(request, exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """参数校验失败 → 422 + 逐字段错误明细。"""
        logger.warning(
            "参数校验失败 %s %s: %s",
            request.method,
            request.url.path,
            "; ".join(
                f"{'.'.join(str(part) for part in error.get('loc', []))}: {error.get('msg')}"
                for error in exc.errors()
            ),
        )
        return JSONResponse(
            status_code=422,
            content=error_payload(
                request,
                "VALIDATION_ERROR",
                "请求参数校验失败",
                exc.errors(),
            ),
        )
