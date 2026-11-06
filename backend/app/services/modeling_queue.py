"""建模任务队列:Redis Stream + consumer group + 心跳租约 + 退避重试 + 死信。

为什么用 Stream 而不是 ``LPUSH/BRPOP``:
list 里的消息一出队就没影了,worker 崩溃/被 kill 时任务直接丢;Stream 有
consumer group 和 PEL(pending entries list),被读走但没 ``XACK`` 的消息仍然
留在组里,进程重启后可以 ``XAUTOCLAIM`` 重新认领。这就是“至少一次”投递的实现基础。

键空间(统一带 ``settings.redis_key_prefix`` 前缀):
==================================================  =======  ==================================
键                                                   类型     作用
==================================================  =======  ==================================
``<p>:modeling:jobs``                                stream   待执行任务(字段 job_id)
``<p>:modeling:delayed``                             zset     退避重试(job_id → 可见时间戳)
``<p>:modeling:dead``                                stream   超过最大重试次数,需人工介入
``<p>:modeling:lease:<job_id>``                      string   运行租约(谁在跑 + 心跳 TTL)
``<p>:modeling:slot:<i>``                            string   分布式并发闸门(i < max_concurrent)
==================================================  =======  ==================================

三层防护各管一件事,别混:

1. **PEL + XAUTOCLAIM**:消息被读走但没 ACK(进程崩了)→ 空闲超过阈值后换人重做;
2. **租约 TTL(lease)**:同一任务同时只允许一个 worker 执行,租约过期才算可抢;
3. **DB 心跳(last_heartbeat_at)**:服务重启后无法从租约判断“上次是谁在跑”,用 DB
   心跳判断僵死并重新入队(见 modeling_service.recoverable_modeling_jobs)。
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import socket
import time
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis, keys

logger = get_logger("app.modeling.queue")

GROUP = "modeling-workers"
STREAM_MAXLEN = 10000
CONSUMER_NAME = f"{socket.gethostname()}-{os.getpid()}"


# --------------------------------------------------------------------------- 键


def stream_key() -> str:
    """待执行任务 Stream 的键。"""
    return keys("modeling", "jobs")


def delayed_key() -> str:
    """退避重试 ZSet 的键（score=可见时间戳）。"""
    return keys("modeling", "delayed")


def dead_key() -> str:
    """死信 Stream 的键。"""
    return keys("modeling", "dead")


def lease_key(job_id: str) -> str:
    """任务运行租约的键（值=持有者 token）。"""
    return keys("modeling", "lease", job_id)


def slot_key(index: int) -> str:
    """第 index 个分布式并发槽位的键。"""
    return keys("modeling", "slot", index)


# ------------------------------------------------------------------- 投递与租约


async def enqueue_modeling_job(job_id: str) -> bool:
    """把任务丢进 Stream。Redis 不可用时返回 False(调用方退回进程内执行)。"""
    redis = await get_redis()
    if redis is None:
        return False
    try:
        await redis.xadd(
            stream_key(),
            {"job_id": job_id},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
    except Exception as exc:  # noqa: BLE001 - Redis 故障要降级而不是让上传失败
        logger.warning("投递建模任务到 Redis 失败(%s),退回进程内执行", exc)
        return False
    return True


async def enqueue_after_delay(job_id: str, delay_seconds: float) -> None:
    """延迟重投:写进 ZSet,由 promoter 到期搬回 Stream(Stream 本身不支持延迟)。"""
    redis = await get_redis()
    if redis is None:
        return
    score = datetime.now(UTC).timestamp() + max(0.0, delay_seconds)
    await redis.zadd(delayed_key(), {job_id: score})


async def bury(job_id: str, reason: str | None) -> None:
    """进死信队列:任务不再自动重试,留给人工排查/一键重试。"""
    redis = await get_redis()
    if redis is None:
        return
    await redis.xadd(
        dead_key(),
        {
            "job_id": job_id,
            "reason": (reason or "未知错误")[:1500],
            "at": datetime.now(UTC).isoformat(),
        },
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )


async def acquire_lease(job_id: str) -> str | None:
    """抢任务租约。返回 token 表示抢到,None 表示别的 worker 正在跑。"""
    redis = await get_redis()
    if redis is None:
        return None
    token = f"{CONSUMER_NAME}:{datetime.now(UTC).timestamp():.0f}"
    acquired = await redis.set(
        lease_key(job_id),
        token,
        nx=True,
        px=settings.modeling_heartbeat_ttl_seconds * 1000,
    )
    return token if acquired else None


async def refresh_lease(job_id: str, token: str) -> bool:
    """续租(只续自己那把:值不匹配说明已被别人接手)。"""
    redis = await get_redis()
    if redis is None:
        return False
    current = await redis.get(lease_key(job_id))
    if current != token:
        return False
    return bool(await redis.pexpire(lease_key(job_id), settings.modeling_heartbeat_ttl_seconds * 1000))


async def release_lease(job_id: str, token: str) -> None:
    """释放租约（只释放自己持有的；被别人接手后不动）。"""
    redis = await get_redis()
    if redis is None:
        return
    current = await redis.get(lease_key(job_id))
    if current == token:
        await redis.delete(lease_key(job_id))


# --------------------------------------------------------------- 分布式并发阀


def slot_ttl_ms() -> int:
    """槽位租约时长。

    必须**短**(按心跳量级),不能取"任务超时时间":worker 被强杀后 TTL 没到期之前,
    这个槽位会一直占着,整个队列(尤其 max_concurrent=1 时)会被一个死进程堵住
    半分钟以上。持有者活着就靠心跳续期,所以短 TTL 不会误伤长任务。
    """
    return max(30, settings.modeling_heartbeat_ttl_seconds * 4) * 1000


async def acquire_slot() -> int | None:
    """抢一个并发槽位(跨进程生效,替代进程内 asyncio.Semaphore)。

    持有者崩溃时槽位靠 TTL 自动释放,不需要额外的清理逻辑。
    """
    redis = await get_redis()
    if redis is None:
        return None
    for index in range(max(1, settings.modeling_max_concurrent)):
        if await redis.set(slot_key(index), CONSUMER_NAME, nx=True, px=slot_ttl_ms()):
            return index
    return None


async def refresh_slot(index: int) -> bool:
    """续租槽位(长任务必须定期续,否则 TTL 到期会被别人抢走)。"""
    redis = await get_redis()
    if redis is None:
        return False
    current = await redis.get(slot_key(index))
    if current != CONSUMER_NAME:
        return False
    return bool(await redis.pexpire(slot_key(index), slot_ttl_ms()))


async def release_slot(index: int) -> None:
    """释放并发槽位（任务结束/异常时都要调用）。"""
    redis = await get_redis()
    if redis is None:
        return
    await redis.delete(slot_key(index))


async def wait_for_slot(poll_seconds: float = 1.0) -> int | None:
    """等到有槽位为止(Redis 不可用时返回 None,由调用方自行降级)。

    背压在这里而不是在"读消息前":任务已经读进 PEL,排队期间消息不会丢,进程崩了
    也有别的 worker 认领。等待过程每 60s 打一条日志,方便判断"是不是被僵死槽位堵住"。
    """
    waited = 0.0
    while True:
        index = await acquire_slot()
        if index is not None:
            return index
        if await get_redis() is None:
            return None
        await asyncio.sleep(poll_seconds)
        waited += poll_seconds
        if waited % 60 < poll_seconds:
            logger.warning(
                "等待建模并发槽位已 %.0fs(max_concurrent=%d),若持续过久请检查是否有僵死 worker",
                waited,
                settings.modeling_max_concurrent,
            )


# ------------------------------------------------------------------- 重试策略


def backoff_seconds(attempts: int) -> float:
    """指数退避:a=1 → base,a=2 → 2×base,a=3 → 4×base。"""
    base = max(0.5, float(settings.modeling_retry_backoff_seconds))
    return base * float(2 ** max(0, attempts - 1))


async def handle_failure(job_id: str, error: str | None) -> str:
    """失败处置:还能重试就进延迟队列,超过上限就进死信。返回 ``retried``/``dead``。"""
    from app.services.modeling_service import mark_job_dead, prepare_retry

    attempts = await prepare_retry(job_id, error, 0.0)
    if attempts is None:
        return "dead"
    if attempts >= settings.modeling_max_attempts:
        await mark_job_dead(job_id, error)
        await bury(job_id, error)
        logger.warning("建模任务 %s 已达最大重试次数(%d),进死信", job_id, attempts)
        return "dead"
    delay = backoff_seconds(attempts)
    await prepare_retry(job_id, error, delay)
    await enqueue_after_delay(job_id, delay)
    logger.info("建模任务 %s 第 %d 次失败,%.1fs 后重试: %s", job_id, attempts, delay, error)
    return "retried"


# --------------------------------------------------------------------- worker


class ModelingWorker:
    """单个 consumer:认领 → 执行 → ACK。进程内只应有一个实例(lifespan 里起)。"""

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._consumer = CONSUMER_NAME

    async def _ensure_group(self, redis) -> bool:
        """幂等创建 consumer group。"""
        try:
            await redis.xgroup_create(stream_key(), GROUP, id="0", mkstream=True)
        except Exception as exc:  # noqa: BLE001 - 组已存在时 Redis 报 BUSYGROUP
            if "BUSYGROUP" in str(exc):
                return True
            logger.warning("创建 consumer group 失败: %s", exc)
            return False
        return True

    # -------------------------------------------------------------- 生命周期
    async def start(self) -> bool:
        """启动 consume/promote 两个循环；Redis 不可用返回 False（进程内降级）。"""
        redis = await get_redis()
        if redis is None:
            logger.warning("Redis 未启用,建模任务队列 worker 不启动(走进程内降级路径)")
            return False
        if not await self._ensure_group(redis):
            return False
        self._stop.clear()
        self._tasks = [
            asyncio.create_task(self._consume_loop(), name="modeling-consume"),
            asyncio.create_task(self._promote_loop(), name="modeling-promote"),
        ]
        logger.info("建模任务队列 worker 已启动 consumer=%s", self._consumer)
        return True

    async def stop(self) -> None:
        """停止所有循环并等待任务收尾（lifespan shutdown 调用）。"""
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks = []

    # ------------------------------------------------------------------ 循环
    async def _consume_loop(self) -> None:
        """主循环：优先认领僵死消息（XAUTOCLAIM），否则读新消息（XREADGROUP）。"""
        while not self._stop.is_set():
            redis = await get_redis()
            if redis is None:
                await asyncio.sleep(1.0)
                continue
            try:
                message = await self._claim_abandoned(redis)
                if message is None:
                    message = await self._read_new(redis)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - 单轮异常不该打死 worker
                if "NOGROUP" in str(exc):
                    # stream/消费组被外部删掉(运维清理、Redis 重启丢数据)时重建,
                    # 否则 worker 会一直空转报错。
                    logger.warning("consumer group 丢失,重建")
                    await self._ensure_group(redis)
                else:
                    logger.warning("读队列失败,%.1fs 后重试: %s", 1.0, exc)
                await asyncio.sleep(1.0)
                continue
            if message is None:
                continue
            await self._handle(redis, message)

    async def _promote_loop(self) -> None:
        """把到期的延迟任务搬回主 Stream。"""
        while not self._stop.is_set():
            await asyncio.sleep(1.0)
            redis = await get_redis()
            if redis is None:
                continue
            try:
                now = datetime.now(UTC).timestamp()
                due = await redis.zrangebyscore(delayed_key(), "-inf", now, start=0, num=50)
                for job_id in due:
                    if await redis.zrem(delayed_key(), job_id):
                        await redis.xadd(
                            stream_key(),
                            {"job_id": job_id},
                            maxlen=STREAM_MAXLEN,
                            approximate=True,
                        )
                        logger.info("延迟重试到期,重新投递任务 %s", job_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.debug("promote 延迟队列失败: %s", exc)

    # ------------------------------------------------------------- 消息获取
    @staticmethod
    def _first(messages: Any) -> tuple[str, str] | None:
        """从 XREADGROUP/XAUTOCLAIM 的返回结构里取第一条 ``(entry_id, job_id)``。"""
        for _stream, entries in messages or []:
            for entry_id, fields in entries:
                job_id = str(fields.get("job_id") or "").strip()
                if job_id:
                    return entry_id, job_id
        return None

    async def _read_new(self, redis) -> tuple[str, str] | None:
        """阻塞读一条新投递的任务（1s 超时，避免停机信号被卡住）。"""
        messages = await redis.xreadgroup(
            GROUP,
            self._consumer,
            {stream_key(): ">"},
            count=1,
            block=1000,
        )
        return self._first(messages)

    async def _claim_abandoned(self, redis) -> tuple[str, str] | None:
        """认领“被读走但没 ACK”的消息(上一个 worker 崩了)。"""
        result = await redis.xautoclaim(
            stream_key(),
            GROUP,
            self._consumer,
            min_idle_time=settings.modeling_reclaim_idle_ms,
            start_id="0-0",
            count=1,
        )
        claimed = result[1] if isinstance(result, list | tuple) and len(result) > 1 else []
        entry = self._first([(stream_key(), claimed)])
        if entry is not None:
            logger.warning("认领到未 ACK 的僵死任务 %s(entry=%s)", entry[1], entry[0])
        return entry

    # --------------------------------------------------------------- 执行
    @staticmethod
    async def _ack(redis, entry_id: str) -> None:
        """ACK + 删条目:ACK 只把消息从 PEL 里拿掉,条目本身还在 Stream 里,
        不删的话 ``XLEN`` 会把“已完成的”也算成积压,而且会一直增长。"""
        await redis.xack(stream_key(), GROUP, entry_id)
        await redis.xdel(stream_key(), entry_id)

    async def _handle(self, redis, message: tuple[str, str]) -> None:
        """执行一条消息：抢租约 → 等并发槽位 → 跑任务 → 按结果 ACK/重试/死信。

        任何路径最终都会 ACK（包括跳过与失败安排重试后），消息不会滞留在 PEL；
        执行期间由 ``_heartbeat`` 协程同时续租约与 DB 心跳。
        """
        from app.core.metrics import record_job_result
        from app.services.modeling_service import JobOutcome, run_modeling_job

        entry_id, job_id = message
        started = time.monotonic()
        token = await acquire_lease(job_id)
        if token is None:
            # 别的 worker 正在跑同一个任务:ACK 掉自己手里的重复投递,不重复建模。
            logger.info("任务 %s 已有 worker 持有租约,跳过本次投递", job_id)
            await self._ack(redis, entry_id)
            return
        slot = await wait_for_slot()
        heartbeat = asyncio.create_task(self._heartbeat(job_id, token, slot))
        try:
            outcome = await run_modeling_job(job_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - 未预期异常同样按失败处理
            logger.exception("执行建模任务 %s 抛出未预期异常", job_id)
            outcome = JobOutcome("failed", f"{type(exc).__name__}: {exc}")
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await heartbeat
            if slot is not None:
                await release_slot(slot)
            await release_lease(job_id, token)
        record_job_result(outcome.status, time.monotonic() - started)

        if outcome.status == "completed":
            await self._ack(redis, entry_id)
            return
        if outcome.status == "skipped":
            # 已经完成/已判死:重复投递直接 ACK 丢弃。
            await self._ack(redis, entry_id)
            return
        result = await handle_failure(job_id, outcome.error)
        await self._ack(redis, entry_id)
        if result == "retried":
            logger.info("任务 %s 已安排重试", job_id)

    async def _heartbeat(self, job_id: str, token: str, slot: int | None = None) -> None:
        """续租约 + 刷 DB 心跳,两个都要,缺一不可:

        - 租约让“同一任务不被两个 worker 同时跑”;
        - DB 心跳让重启后的 ``recoverable_modeling_jobs`` 能分辨僵死任务。
        """
        from app.services.modeling_service import set_job_heartbeat

        interval = max(1.0, settings.modeling_heartbeat_ttl_seconds / 3)
        while True:
            await asyncio.sleep(interval)
            try:
                if not await refresh_lease(job_id, token):
                    logger.warning("任务 %s 租约丢失(可能被判僵死),停止心跳", job_id)
                    return
                # 槽位与租约一起续:长任务(可达 30 分钟)不能因为槽位 TTL 到期被抢。
                if slot is not None:
                    await refresh_slot(slot)
                await set_job_heartbeat(job_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.debug("刷新任务 %s 心跳失败: %s", job_id, exc)


_worker: ModelingWorker | None = None


async def start_modeling_worker() -> bool:
    """启动进程级单例 worker（已启动则幂等返回 True）。"""
    global _worker
    if _worker is not None:
        return True
    _worker = ModelingWorker()
    started = await _worker.start()
    if not started:
        _worker = None
    return started


async def stop_modeling_worker() -> None:
    """停掉单例 worker（未启动时为空操作）。"""
    global _worker
    worker, _worker = _worker, None
    if worker is not None:
        await worker.stop()


async def queue_stats() -> dict[str, Any]:
    """队列水位(前端/运维看积压用;Redis 不可用时返回 ``ready=False``)。"""
    redis = await get_redis()
    if redis is None:
        return {"ready": False}
    try:
        pending = await redis.xpending(stream_key(), GROUP)
        return {
            "ready": True,
            "stream_length": await redis.xlen(stream_key()),
            "delayed": await redis.zcard(delayed_key()),
            "dead": await redis.xlen(dead_key()),
            "pending": int(pending.get("pending", 0)) if isinstance(pending, dict) else 0,
        }
    except Exception as exc:  # noqa: BLE001
        if "NOGROUP" in str(exc):
            # 队列尚未初始化(还没投递过任何任务):各水位就是 0。
            return {"ready": True, "stream_length": 0, "delayed": 0, "dead": 0, "pending": 0}
        return {"ready": False, "error": str(exc)}


async def recover_pending_jobs() -> int:
    """服务启动时的自愈:把上次进程死掉的 pending/running 任务重新入队。

    与“一律判死”的旧行为相比,重启不再丢任务:只要还没超过最大重试次数就重投,
    超过的进死信等待人工处理。返回重新投递的任务数。
    """
    from app.services.modeling_service import mark_job_dead, recoverable_modeling_jobs

    rows = await recoverable_modeling_jobs(settings.modeling_heartbeat_ttl_seconds)
    requeued = 0
    for job_id, attempts in rows:
        if attempts >= settings.modeling_max_attempts:
            await mark_job_dead(job_id, "服务重启恢复时已超过最大重试次数")
            await bury(job_id, "重启恢复时超过最大重试次数")
            continue
        if await enqueue_modeling_job(job_id):
            requeued += 1
    if rows:
        logger.warning(
            "启动恢复:%d 个中断任务,其中 %d 个已重新入队", len(rows), requeued
        )
    return requeued
