"""数据库引擎与会话工厂（SQLAlchemy 2.0 async + asyncmy）。

``get_db_session`` 通过 ``app.api.dependencies.DbSession`` 注入到所有路由；
需要在请求会话之外访问数据库的地方（队列 worker、SSE 循环、恢复逻辑）直接
用 ``AsyncSessionFactory`` 开短会话，避免长期占用连接池。
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """全部 ORM 模型的声明基类（alembic 以此收集元数据）。"""


engine = create_async_engine(
    settings.database_url,
    # 单独的 DB_ECHO 开关:DEBUG 只影响 FastAPI/异常详情,不再顺带打印 SQL。
    echo=settings.db_echo,
    echo_pool="debug" if settings.db_echo else False,
    pool_pre_ping=True,
    pool_recycle=1800,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：请求级会话（随请求结束自动关闭，无自动 commit）。"""
    async with AsyncSessionFactory() as session:
        yield session
