"""建模任务队列:投递/租约/并发闸门/退避重试/死信/崩溃自愈。

用 fakeredis 跑真 Redis 命令(stream/consumer group/XAUTOCLAIM),只有需要落库的
重试与死信用例才连 MySQL(不可用时自动 skip)。
"""
from __future__ import annotations

from datetime import timedelta

import db_utils  # noqa: E402 - tests 目录以 rootdir 加入 sys.path
import pytest

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.models.modeling import ModelingJob
from app.services.modeling_queue import (
    GROUP,
    ModelingWorker,
    acquire_lease,
    acquire_slot,
    backoff_seconds,
    bury,
    dead_key,
    delayed_key,
    enqueue_modeling_job,
    handle_failure,
    lease_key,
    recover_pending_jobs,
    refresh_lease,
    release_lease,
    release_slot,
    slot_key,
    stream_key,
)
from app.services.modeling_service import JobOutcome, run_modeling_job


class TestSlotLease:
    """槽位租约语义:短 TTL + 心跳续期。"""

    async def test_slot_ttl_is_short_enough_to_self_heal(self) -> None:
        """槽位 TTL 必须按心跳量级,不能取任务超时(否则死 worker 会堵住队列半小时)。"""
        from app.services.modeling_queue import slot_ttl_ms

        assert slot_ttl_ms() <= 5 * 60 * 1000, "槽位租约不应超过 5 分钟"
        assert slot_ttl_ms() >= 30 * 1000, "太短会让长任务在两次心跳之间丢掉槽位"

    async def test_slot_is_refreshed_while_running(self, fake_redis, monkeypatch) -> None:
        from app.services.modeling_queue import refresh_slot

        monkeypatch.setattr(settings, "modeling_max_concurrent", 1)
        index = await acquire_slot()
        assert index == 0
        await fake_redis.pexpire(slot_key(0), 1000)  # 模拟快要过期
        assert await refresh_slot(0) is True
        ttl = await fake_redis.pttl(slot_key(0))
        assert ttl > 1000, "心跳续期必须把槽位 TTL 拉长"


@pytest.fixture(autouse=True)
def _fast_reclaim(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试里不需要等 60s 才认领僵死消息。"""
    monkeypatch.setattr(settings, "modeling_reclaim_idle_ms", 0)


async def _create_group(redis) -> None:
    await redis.xgroup_create(stream_key(), GROUP, id="0", mkstream=True)


class TestEnqueue:
    async def test_enqueue_writes_to_stream(self, fake_redis) -> None:
        assert await enqueue_modeling_job("job-1") is True
        assert await fake_redis.xlen(stream_key()) == 1
        entries = await fake_redis.xrange(stream_key())
        assert entries[0][1]["job_id"] == "job-1"

    async def test_enqueue_returns_false_when_redis_disabled(self, monkeypatch) -> None:
        from app.core import redis_client

        redis_client.set_redis_for_tests(None)
        monkeypatch.setattr(settings, "redis_enabled", False)
        try:
            assert await enqueue_modeling_job("job-1") is False
        finally:
            monkeypatch.setattr(settings, "redis_enabled", True)


class TestSlots:
    async def test_slots_are_limited_across_processes(self, fake_redis, monkeypatch) -> None:
        monkeypatch.setattr(settings, "modeling_max_concurrent", 1)
        first = await acquire_slot()
        assert first == 0
        assert await acquire_slot() is None, "max_concurrent=1 时第二个必须拿不到槽位"

        await release_slot(first)
        assert await acquire_slot() == 0
        assert await fake_redis.exists(slot_key(0)) == 1

    async def test_slot_scales_with_max_concurrent(self, fake_redis, monkeypatch) -> None:
        monkeypatch.setattr(settings, "modeling_max_concurrent", 3)
        assert [await acquire_slot() for _ in range(3)] == [0, 1, 2]
        assert await acquire_slot() is None


class TestLease:
    async def test_lease_is_exclusive_and_myopic(self, fake_redis) -> None:
        token = await acquire_lease("job-1")
        assert token is not None
        assert await acquire_lease("job-1") is None, "同一任务不能被两个 worker 同时持有"

        assert await refresh_lease("job-1", "别的-token") is False, "只能续自己那把锁"
        assert await refresh_lease("job-1", token) is True

        await release_lease("job-1", token)
        assert await fake_redis.exists(lease_key("job-1")) == 0
        assert await acquire_lease("job-1") is not None


class TestBackoff:
    def test_backoff_grows_exponentially(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "modeling_retry_backoff_seconds", 5.0)
        assert backoff_seconds(1) == 5.0
        assert backoff_seconds(2) == 10.0
        assert backoff_seconds(3) == 20.0


class TestFailureHandling:
    async def test_failure_schedules_retry_with_backoff(self, fake_redis) -> None:
        await db_utils.open_or_skip()
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(session, project.id, status="running", attempts=1)

                outcome = await handle_failure(job.id, "引擎炸了")

                assert outcome == "retried"
                fresh = await db_utils.fetch_job(job.id)
                assert fresh is not None
                assert fresh.status == "pending", "未超上限时应回到排队态等待重投"
                assert fresh.next_retry_at is not None
                assert (await fake_redis.zscore(delayed_key(), job.id)) is not None
                assert await fake_redis.xlen(dead_key()) == 0
            finally:
                await db_utils.drop_project(project.id)

    async def test_failure_over_limit_goes_to_dead_letter(self, fake_redis, monkeypatch) -> None:
        await db_utils.open_or_skip()
        monkeypatch.setattr(settings, "modeling_max_attempts", 3)
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(session, project.id, status="running", attempts=3)

                outcome = await handle_failure(job.id, "还是炸")

                assert outcome == "dead"
                fresh = await db_utils.fetch_job(job.id)
                assert fresh is not None
                assert fresh.status == "failed"
                assert "已重试 3 次" in (fresh.error_message or "")
                dead = await fake_redis.xrange(dead_key())
                assert dead and dead[0][1]["job_id"] == job.id
                assert (await fake_redis.zscore(delayed_key(), job.id)) is None
            finally:
                await db_utils.drop_project(project.id)


class TestWorkerRecovery:
    async def test_abandoned_message_can_be_claimed_after_crash(self, fake_redis) -> None:
        """消息被读走但没 ACK(worker 被 kill)时,必须还能被别人认领 —— 这就是
        “至少一次投递”的来源,也是 list 方案做不到的地方。"""
        await _create_group(fake_redis)
        await enqueue_modeling_job("job-1")

        # 模拟崩溃的 worker:读进 PEL 但不 ACK
        crashed = await fake_redis.xreadgroup(
            GROUP, "crashed-worker", {stream_key(): ">"}, count=1
        )
        assert crashed[0][1][0][1]["job_id"] == "job-1"

        worker = ModelingWorker()
        claimed = await worker._claim_abandoned(fake_redis)

        assert claimed is not None and claimed[1] == "job-1"

    async def test_handle_acks_completed_job(self, fake_redis, monkeypatch) -> None:
        await _create_group(fake_redis)
        await enqueue_modeling_job("job-1")
        message = await ModelingWorker()._read_new(fake_redis)
        assert message is not None

        calls: list[str] = []

        async def fake_run(job_id: str) -> JobOutcome:
            calls.append(job_id)
            return JobOutcome("completed")

        monkeypatch.setattr("app.services.modeling_service.run_modeling_job", fake_run)

        await ModelingWorker()._handle(fake_redis, message)

        assert calls == ["job-1"], "任务应被执行一次"
        pending = await fake_redis.xpending(stream_key(), GROUP)
        assert int(pending["pending"]) == 0, "成功后必须 ACK,否则消息会一直被重认领"
        assert await fake_redis.xlen(stream_key()) == 0, "完成后条目也应删除,否则积压数虚高"
        assert await fake_redis.exists(lease_key("job-1")) == 0, "租约必须释放"

    async def test_handle_skips_when_another_worker_holds_lease(
        self, fake_redis, monkeypatch
    ) -> None:
        await _create_group(fake_redis)
        await enqueue_modeling_job("job-1")
        message = await ModelingWorker()._read_new(fake_redis)
        assert message is not None
        await acquire_lease("job-1")  # 别的 worker 正在跑

        calls: list[str] = []

        async def fake_run(job_id: str) -> JobOutcome:
            calls.append(job_id)
            return JobOutcome("completed")

        monkeypatch.setattr("app.services.modeling_service.run_modeling_job", fake_run)
        await ModelingWorker()._handle(fake_redis, message)

        assert calls == [], "租约被别人持有时不能重复建模"
        pending = await fake_redis.xpending(stream_key(), GROUP)
        assert int(pending["pending"]) == 0, "重复投递应被 ACK 丢弃"


class TestRestartRecovery:
    async def test_stale_job_is_requeued_on_startup(self, fake_redis) -> None:
        await db_utils.open_or_skip()
        await _create_group(fake_redis)
        stale_heartbeat = db_utils.utc_now() - timedelta(minutes=10)
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(
                    session,
                    project.id,
                    status="running",
                    attempts=1,
                    heartbeat=stale_heartbeat,
                )

                requeued = await recover_pending_jobs()

                assert requeued >= 1
                entries = await fake_redis.xrange(stream_key())
                assert any(fields["job_id"] == job.id for _id, fields in entries)
            finally:
                await db_utils.drop_project(project.id)

    async def test_fresh_heartbeat_is_left_alone(self, fake_redis) -> None:
        await db_utils.open_or_skip()
        await _create_group(fake_redis)
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(
                    session, project.id, status="running", attempts=1,
                    heartbeat=db_utils.utc_now(),
                )

                await recover_pending_jobs()

                entries = await fake_redis.xrange(stream_key())
                assert all(fields["job_id"] != job.id for _id, fields in entries), (
                    "心跳还新的任务说明有 worker 在跑,不能被抢"
                )
            finally:
                await db_utils.drop_project(project.id)

    async def test_job_over_attempts_goes_dead_on_recovery(self, fake_redis, monkeypatch) -> None:
        await db_utils.open_or_skip()
        await _create_group(fake_redis)
        monkeypatch.setattr(settings, "modeling_max_attempts", 2)
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(
                    session, project.id, status="running", attempts=2,
                    heartbeat=db_utils.utc_now() - timedelta(minutes=10),
                )

                await recover_pending_jobs()

                fresh = await db_utils.fetch_job(job.id)
                assert fresh is not None
                assert fresh.status == "failed"
                dead = await fake_redis.xrange(dead_key())
                assert any(fields["job_id"] == job.id for _id, fields in dead)
            finally:
                await db_utils.drop_project(project.id)


class TestRunModelingJobGuard:
    async def test_finished_job_is_skipped(self, fake_redis) -> None:
        """重复投递已完成任务时必须直接跳过(幂等),不能重跑一遍 25s 建模。"""
        await db_utils.open_or_skip()
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(session, project.id, status="completed")

                outcome = await run_modeling_job(job.id)

                assert outcome.status == "skipped"
            finally:
                await db_utils.drop_project(project.id)

    async def test_missing_job_is_skipped(self, fake_redis) -> None:
        await db_utils.open_or_skip()
        outcome = await run_modeling_job("00000000-0000-0000-0000-000000000000")
        assert outcome.status == "skipped"

    async def test_bury_is_optional_on_plain_failure(self, fake_redis) -> None:
        """bury 单独可用(运维/脚本手动把任务打进死信)。"""
        await bury("job-x", "手动放弃")
        dead = await fake_redis.xrange(dead_key())
        assert dead[0][1]["reason"] == "手动放弃"


class TestJobRowModel:
    async def test_attempts_defaults_to_zero(self) -> None:
        job = ModelingJob(project_id="p", params_json={}, input_strata_path="a",
                          input_location_path="b")
        assert job.attempts in (None, 0) or job.attempts == 0
