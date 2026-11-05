"""pytest 共享夹具。

``fake_redis`` 用 fakeredis 在内存里模拟 Redis,让任务队列/进度推送/分析缓存的
测试不需要真实 Redis 服务(CI 与本地都不需要先 ``docker compose up -d``)。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
import pytest_asyncio

from app.core import redis_client
from app.core.database import engine


@pytest.fixture(autouse=True)
async def _dispose_db_engine():
    """pytest-asyncio 每个用例一个事件循环,连接池必须跟着清,否则下一个用例会拿到
    绑在已关闭 loop 上的连接(sqlalchemy.exc.InvalidPoolError / Event loop is closed)。"""
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    """注入 fakeredis 作为全局 Redis 客户端,用例结束后自动清理。"""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_client.set_redis_for_tests(client)
    try:
        yield client
    finally:
        redis_client.clear_redis_for_tests()
        try:
            await client.flushall()
            await client.aclose()
        except Exception:  # noqa: BLE001 - 清理阶段不掩盖真实断言失败
            pass


@pytest.fixture
def redis_prefix() -> str:
    """键空间前缀(与 settings.redis_key_prefix 一致),用例拼键名用。"""
    from app.core.config import settings

    return settings.redis_key_prefix
