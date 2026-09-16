from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger


logger = get_logger("app.errors")


class AppError(Exception):
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
    return {
        "code": code,
        "message": message,
        "details": details,
        "requestId": getattr(request.state, "request_id", None),
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
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
