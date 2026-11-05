"""SSE 实时进度:快照读写、事件续传(Last-Event-ID)、终态收尾。

用 httpx 的 ASGITransport 直接跑 ASGI 应用(不起真端口、不跑 lifespan),
这样断线/续传这类时序场景可以精确构造。
"""
from __future__ import annotations

import asyncio
import json

import db_utils
import httpx
import pytest
from sqlalchemy import text

from app.core.database import AsyncSessionFactory
from app.main import app
from app.services.modeling_progress import (
    PROGRESS_TTL_SECONDS,
    read_events,
    read_progress,
    record_progress,
    snapshot_key,
    stream_key,
)
from app.services.modeling_service import run_modeling_job


@pytest.fixture
async def client(fake_redis):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _parse_sse(raw: str) -> list[dict[str, str]]:
    """把 SSE 文本切成帧(只关心 id/event/data)。"""
    frames: list[dict[str, str]] = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        frame: dict[str, str] = {}
        for line in block.splitlines():
            if line.startswith(":"):
                frame.setdefault("comment", line)
                continue
            field, _, value = line.partition(": ")
            frame[field] = value
        frames.append(frame)
    return frames


class TestProgressSnapshot:
    async def test_record_and_read_snapshot(self, fake_redis) -> None:
        entry_id = await record_progress("job-1", "界面插值", 21.5, "界面插值 5/15")

        assert entry_id is not None
        snapshot = await read_progress("job-1")
        assert snapshot == {"stage": "界面插值", "percent": 21.5, "message": "界面插值 5/15"}
        assert await fake_redis.ttl(snapshot_key("job-1")) == PROGRESS_TTL_SECONDS

    async def test_percent_is_clamped_and_message_flattened(self, fake_redis) -> None:
        await record_progress("job-1", "建模中", 180, "多行\n输出")
        snapshot = await read_progress("job-1")
        assert snapshot is not None
        assert snapshot["percent"] == 100.0
        assert "\n" not in snapshot["message"], "SSE 帧不能被多行消息撕断"

    async def test_read_progress_returns_none_without_data(self, fake_redis) -> None:
        assert await read_progress("不存在的任务") is None

    async def test_events_can_be_resumed_after_last_id(self, fake_redis) -> None:
        first = await record_progress("job-1", "解析输入", 5, "解析完成")
        second = await record_progress("job-1", "界面插值", 30, "界面插值 8/15")
        third = await record_progress("job-1", "导出交付包", 88, "导出 L14")

        later = await read_events("job-1", first)
        assert [entry[0] for entry in later] == [second, third], (
            "续传必须从 Last-Event-ID 之后开始,不能重发也不能漏发"
        )

        latest = await read_events("job-1", None)
        assert [entry[0] for entry in latest] == [third], "首次连接只补最近一帧(历史由快照代表)"


class TestSseEndpoint:
    async def test_stream_sends_snapshot_then_progress_then_done(self, client, fake_redis) -> None:
        await db_utils.open_or_skip()
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(session, project.id, status="running")
                await record_progress(job.id, "界面插值", 20, "界面插值 4/15")

                async def push_more() -> None:
                    await asyncio.sleep(0.6)
                    await record_progress(job.id, "导出交付包", 85, "导出 L09")
                    await asyncio.sleep(0.6)
                    async with AsyncSessionFactory() as inner:
                        await inner.execute(
                            text("UPDATE modeling_jobs SET status='completed' WHERE id=:i"),
                            {"i": job.id},
                        )
                        await inner.commit()

                pusher = asyncio.create_task(push_more())
                async with client.stream("GET", f"/api/v1/modeling-jobs/{job.id}/events") as response:
                    assert response.status_code == 200
                    assert response.headers["content-type"].startswith("text/event-stream")
                    assert response.headers["x-accel-buffering"] == "no"
                    body = "".join([chunk async for chunk in response.aiter_text()])
                await pusher

                frames = _parse_sse(body)
                progresses = [f for f in frames if f.get("event") == "progress"]
                dones = [f for f in frames if f.get("event") == "done"]

                assert progresses, "至少要推出快照帧与后续进度帧"
                percents = [json.loads(f["data"])["percent"] for f in progresses]
                assert percents[0] == 20.0, "首帧应是当前快照,晚连进来也能看到进度"
                assert 85.0 in percents, "后续事件必须被推出去"
                assert all(f.get("id") for f in progresses), "每条事件都要带 id 供 Last-Event-ID 续传"
                assert dones and json.loads(dones[0]["data"])["percent"] == 100.0
            finally:
                await db_utils.drop_project(project.id)

    async def test_stream_replays_events_after_last_event_id(self, client, fake_redis) -> None:
        await db_utils.open_or_skip()
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(session, project.id, status="completed")
                first = await record_progress(job.id, "解析输入", 5, "解析完成")
                await record_progress(job.id, "完成", 100, "建模完成")

                async with client.stream(
                    "GET",
                    f"/api/v1/modeling-jobs/{job.id}/events",
                    headers={"Last-Event-ID": first},
                ) as response:
                    body = "".join([chunk async for chunk in response.aiter_text()])

                frames = _parse_sse(body)
                progresses = [f for f in frames if f.get("event") == "progress"]
                assert [json.loads(f["data"])["stage"] for f in progresses] == ["完成"], (
                    "带 Last-Event-ID 重连时只补发之后的事件"
                )
                assert any(f.get("event") == "done" for f in frames)
            finally:
                await db_utils.drop_project(project.id)

    async def test_unknown_job_returns_404(self, client, fake_redis) -> None:
        await db_utils.open_or_skip()
        response = await client.get("/api/v1/modeling-jobs/00000000-0000-0000-0000-000000000000/events")
        assert response.status_code == 404


class TestJobDetailCarriesPercent:
    async def test_get_job_includes_snapshot_percent(self, client, fake_redis) -> None:
        await db_utils.open_or_skip()
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(session, project.id, status="running")
                await record_progress(job.id, "TIN-GTP 建模", 55, "向量化 TIN-GTP 建模中")

                response = await client.get(f"/api/v1/modeling-jobs/{job.id}")

                payload = response.json()["data"]
                assert payload["percent"] == 55.0
                assert payload["stage"] == "TIN-GTP 建模"
            finally:
                await db_utils.drop_project(project.id)

    async def test_completed_job_reports_100_percent(self, client, fake_redis) -> None:
        await db_utils.open_or_skip()
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(session, project.id, status="completed")

                response = await client.get(f"/api/v1/modeling-jobs/{job.id}")

                assert response.json()["data"]["percent"] == 100.0
            finally:
                await db_utils.drop_project(project.id)


class TestEngineProgressParsing:
    """引擎的 ``[progress]`` 行 → Redis 快照:进度解析在建模服务里,这里覆盖解析契约。"""

    def test_engine_reporter_emits_monotonic_percent(self) -> None:
        from modeling_engine.generate import _Reporter

        reporter = _Reporter()
        reporter.layers_total = 2
        reporter.mark("解析输入", 5, "解析完成")
        reporter.report("界面插值 3/15 IF_2_bottom_煤层")
        reporter.report("向量化 TIN-GTP 建模中")
        reporter.report("导出 L01 粉砂岩")
        reporter.report("导出 L02 煤层")

        assert reporter.percent == pytest.approx(78 + 14 * 1.0)
        assert reporter.percent >= 5

    def test_percent_never_goes_backwards(self) -> None:
        from modeling_engine.generate import _Reporter

        reporter = _Reporter()
        reporter.mark("导出交付包", 90, "导出 L10")
        reporter.report("界面插值 1/15 IF_1")  # 更靠前的阶段

        assert reporter.percent == 90, "百分比必须单调不回退,否则进度条会往回跳"

    async def test_run_modeling_job_records_failure_progress(self, fake_redis, monkeypatch) -> None:
        await db_utils.open_or_skip()
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                job = await db_utils.create_job(session, project.id, status="pending")

                async def boom(*_args, **_kwargs):
                    raise RuntimeError("引擎挂了")

                monkeypatch.setattr(
                    "app.services.modeling_service._execute_engine", boom
                )

                outcome = await run_modeling_job(job.id)

                assert outcome.status == "failed"
                snapshot = await read_progress(job.id)
                assert snapshot is not None
                assert snapshot["stage"] == "失败"
                assert await fake_redis.exists(stream_key(job.id)) == 1
                fresh = await db_utils.fetch_job(job.id)
                assert fresh is not None and fresh.attempts == 1
            finally:
                await db_utils.drop_project(project.id)
