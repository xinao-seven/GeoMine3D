"""Redis 客户端封装(懒初始化单例 + 测试注入 + 优雅降级)。

为什么所有调用方都必须容忍 ``None``:
Redis 提供的是"加速与协同"能力(任务队列 / 进度快照 / 结果缓存),不是数据源。
交付包、任务状态、分析结果的真值都在磁盘与 MySQL 里,Redis 整体不可用时后端应当
降级回进程内路径继续工作,而不是 500。因此:

- ``settings.redis_enabled=false`` → ``get_redis()`` 返回 ``None``,调用方走降级分支;
- 起了 Redis 但连不上 → ``ping_redis()`` 返回 ``False`` 并打警告,调用方同样降级;
- 测试用 ``set_redis_for_tests()`` 注入 fakeredis,不依赖真实 Redis 服务。

键空间统一由 ``keys()`` 生成,前缀来自 ``settings.redis_key_prefix``,便于运维用
``SCAN <prefix>:*`` 一次性看清/清理(不使用 ``KEYS``,避免阻塞单线程 Redis)。
"""
from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.redis")

_client: aioredis.Redis | None = None
_test_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis | None:
    """返回进程内复用的 Redis 客户端;未启用或仅供测试时返回对应实例/None。

    注意 ``from_url`` 是惰性的——这里不会真正建连,所以"Redis 没起"不会在启动时炸,
    只在第一次真正执行命令时抛 ``ConnectionError``,由调用方的降级分支承接。
    """
    if _test_client is not None:
        return _test_client
    if not settings.redis_enabled:
        return None
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30,
        )
    return _client


async def ping_redis() -> bool:
    """探活。启动时调用一次,失败只记警告(不影响服务启动)。"""
    client = await get_redis()
    if client is None:
        return False
    try:
        return bool(await client.ping())
    except Exception as exc:  # noqa: BLE001 - 降级路径,任何异常都只当"不可用"
        logger.warning("Redis 不可用(%s),后端将降级为进程内任务与无缓存模式", exc)
        return False


async def close_redis() -> None:
    """关闭客户端(挂 lifespan 的 shutdown 分支)。"""
    global _client
    client, _client = _client, None
    if client is not None:
        try:
            await client.aclose()
        except Exception as exc:  # noqa: BLE001
            logger.debug("关闭 Redis 客户端时忽略异常: %s", exc)


def keys(*parts: Any) -> str:
    """拼接带全局前缀的键名: ``keys("job", job_id)`` → ``geomine:job:<id>``。"""
    return ":".join([settings.redis_key_prefix, *(str(part) for part in parts)])


def set_redis_for_tests(client: aioredis.Redis | None) -> None:
    """注入测试替身(fakeredis);传 None 取消注入。"""
    global _test_client
    _test_client = client


def clear_redis_for_tests() -> None:
    set_redis_for_tests(None)
