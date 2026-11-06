"""分析结果的共享缓存 + single-flight 防击穿。

为什么值得缓存:等值线(IDW 网格 + Marching Squares)、勘探线剖面(逐三角面求交)、
虚拟钻孔(IDW)都是**纯函数**:同样的输入永远同样输出,但每次点击都重算。其中剖面
要读几十 MB 的闭合壳网格,单次几百毫秒。

为什么不缓存到进程内(原来的 ``section_service._MESH_CACHE``):
进程内字典重启即失效、多 worker 之间也不共享,命中的期望值很低。放 Redis 之后
"第一次算完,第二个用户/第二次点击直接命中"。

键怎么定:**按真实输入做哈希**,而不是按"项目 id + 时间戳"。输入一变(换了交付包、
换了钻孔、换了参数)哈希就变,缓存自然失效,不需要猜 TTL 该设多久;TTL 只做兜底清理。

击穿怎么防:未命中时抢一把 ``SET NX PX`` 锁,只有一个请求真正计算,其余请求短暂
轮询缓存;等太久还没好就直接自己算(宁可多算一次,也不能让请求挂死)。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable, Sequence
from typing import Any

from app.core.logging import get_logger
from app.core.metrics import record_cache_hit, record_cache_miss, record_cache_shared
from app.core.redis_client import get_redis, keys

logger = get_logger("app.analysis.cache")

DEFAULT_TTL_SECONDS = 3600
LOCK_TTL_MS = 10_000
WAIT_TIMEOUT_SECONDS = 3.0
POLL_INTERVAL_SECONDS = 0.05


def cache_key(namespace: str, parts: Sequence[Any]) -> str:
    """输入 → 稳定键。参数按 JSON 规范化(排序键)后取 sha256。"""
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return keys("cache", namespace, digest[:32])


def lock_key(key: str) -> str:
    """single-flight 锁的键（在缓存键后追加 ``:lock``）。"""
    return f"{key}:lock"


async def cached_result(
    namespace: str,
    parts: Sequence[Any],
    compute: Callable[[], Any],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> Any:
    """带缓存与 single-flight 的纯计算。

    ``compute`` 是同步函数(重 CPU/重 IO),在 ``asyncio.to_thread`` 里跑,避免阻塞
    事件循环 —— 这一点很关键:SSE 长连接与建模子进程的输出泵都在同一个 loop 上。
    """
    redis = await get_redis()
    if redis is None:
        record_cache_miss(namespace, reason="no_redis")
        return await asyncio.to_thread(compute)

    key = cache_key(namespace, parts)
    cached = await _read(redis, key)
    if cached is not None:
        record_cache_hit(namespace)
        return cached

    owner = await _acquire_lock(redis, key)
    if owner:
        try:
            # 抢到锁之后再读一次:可能上一个持有者刚写完。
            cached = await _read(redis, key)
            if cached is not None:
                record_cache_hit(namespace)
                return cached
            record_cache_miss(namespace)
            value = await asyncio.to_thread(compute)
            await _write(redis, key, value, ttl_seconds)
            return value
        finally:
            await _release_lock(redis, key)

    # 别人正在算:短暂等待它的结果,超时就自己算(防饿死)。
    waited = 0.0
    while waited < WAIT_TIMEOUT_SECONDS:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        waited += POLL_INTERVAL_SECONDS
        cached = await _read(redis, key)
        if cached is not None:
            record_cache_hit(namespace)
            record_cache_shared(namespace)
            return cached
    record_cache_miss(namespace, reason="lock_timeout")
    return await asyncio.to_thread(compute)


async def _read(redis, key: str) -> Any | None:
    """读缓存并反序列化；Redis 故障/JSON 损坏一律按未命中处理。"""
    try:
        raw = await redis.get(key)
    except Exception as exc:  # noqa: BLE001 - 缓存读失败按未命中处理
        logger.debug("读缓存失败 %s: %s", key, exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


async def _write(redis, key: str, value: Any, ttl_seconds: int) -> None:
    """写缓存（失败只记 debug，不影响本次请求结果）。"""
    try:
        await redis.set(key, json.dumps(value, ensure_ascii=False), ex=max(1, ttl_seconds))
    except Exception as exc:  # noqa: BLE001 - 写缓存失败不影响本次结果
        logger.debug("写缓存失败 %s: %s", key, exc)


async def _acquire_lock(redis, key: str) -> bool:
    """抢 single-flight 锁（SET NX PX；故障时按"没抢到"处理，不会挡住计算）。"""
    try:
        return bool(await redis.set(lock_key(key), "1", nx=True, px=LOCK_TTL_MS))
    except Exception:  # noqa: BLE001
        return False


async def _release_lock(redis, key: str) -> None:
    """释放 single-flight 锁（永远静默，不掩盖计算阶段的异常）。"""
    try:
        await redis.delete(lock_key(key))
    except Exception:  # noqa: BLE001
        pass


async def invalidate_namespace(namespace: str) -> int:
    """清掉某命名空间的全部缓存(手工重跑/数据修复后用)。返回删除条数。"""
    redis = await get_redis()
    if redis is None:
        return 0
    pattern = keys("cache", namespace, "*")
    removed = 0
    async for key in redis.scan_iter(match=pattern, count=200):
        removed += int(await redis.delete(key))
    return removed
