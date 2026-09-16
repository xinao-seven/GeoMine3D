"""集中式日志配置。

目标:让后端输出**有条理、可检索**的日志。

- 统一格式：时间 | 级别 | logger 名称 | requestId | 内容，级别与名称定宽对齐，便于肉眼扫读。
- 统一出口：全部写 stdout(容器/重定向友好),不额外写文件。
- 分层控制：应用日志走 `app.*`,SQLAlchemy 的 SQL 语句默认**关闭**,由 `DB_ECHO` 单独开关。
- 请求关联：中间件把 requestId 写入 contextvar,格式器自动附加,可与响应头 `X-Request-ID` 对上。
- 去重：禁用 uvicorn 自带的 access 日志,由 `app.access` 统一输出一行结构化访问日志。
"""

from __future__ import annotations

import logging
import logging.config
from contextvars import ContextVar

from app.core.config import settings


# 当前请求的关联 ID;不在请求上下文时用 "-" 占位。
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# 控制台日志格式:级别 8 列、logger 名 26 列,保证列对齐。
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-26s | rid=%(request_id)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RequestIdFilter(logging.Filter):
    """把 contextvar 中的 requestId 注入每条日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


# 需要压噪的第三方 logger:默认只保留 WARNING 及以上。
NOISY_LOGGERS = {
    "sqlalchemy": "WARNING",
    "sqlalchemy.engine": "WARNING",
    "sqlalchemy.pool": "WARNING",
    "sqlalchemy.dialects": "WARNING",
    "asyncmy": "WARNING",
    "aiomysql": "WARNING",
    "watchfiles": "WARNING",
    "watchfiles.main": "WARNING",
    "multipart": "WARNING",
    "python_multipart": "WARNING",
    "httpx": "WARNING",
    "httpcore": "WARNING",
    "asyncio": "WARNING",
}


def build_logging_config() -> dict:
    level = settings.log_level.upper()
    # SQL 语句是否输出取决于 DB_ECHO,而不是 DEBUG,避免调试模式下刷屏。
    sqlalchemy_level = "INFO" if settings.db_echo else "WARNING"
    noisy = {**NOISY_LOGGERS, "sqlalchemy.engine": sqlalchemy_level, "sqlalchemy": sqlalchemy_level}

    return {
        "version": 1,
        # 关键:不要禁用已有 logger,否则会关掉 uvicorn 自己的启动日志。
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "app.core.logging.RequestIdFilter"},
        },
        "formatters": {
            "standard": {
                "format": LOG_FORMAT,
                "datefmt": DATE_FORMAT,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "standard",
                "filters": ["request_id"],
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "loggers": {
            # 应用日志:唯一的业务日志出口(app.api / app.services / app.core ...)。
            "app": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
            # 访问日志:由 main.request_context 中间件输出,这里只负责级别。
            "app.access": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
            # uvicorn 服务日志(启动/关闭/错误)保留;access 交给 app.access。
            "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["console"], "level": "WARNING", "propagate": False},
            **{
                name: {"handlers": ["console"], "level": logger_level, "propagate": False}
                for name, logger_level in noisy.items()
            },
        },
    }


_configured = False


def setup_logging() -> None:
    """初始化日志配置(幂等)。应在 FastAPI app 创建前调用。"""

    global _configured
    if _configured:
        return
    logging.config.dictConfig(build_logging_config())
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
