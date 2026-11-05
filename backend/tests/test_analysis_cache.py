"""分析结果共享缓存:命中、single-flight 防击穿、输入变化自然失效、Redis 故障降级。

另外覆盖 ``/metrics`` 端点确实暴露了缓存与建模任务指标。
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core import redis_client
from app.main import app
from app.services.analysis_cache import (
    cache_key,
    cached_result,
    invalidate_namespace,
    lock_key,
)


@pytest.fixture
async def client(fake_redis):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


class TestCacheKey:
    def test_key_is_stable_for_same_input(self) -> None:
        a = cache_key("contours", ["L01", 5, [{"x": 1, "y": 2, "value": 3}]])
        b = cache_key("contours", ["L01", 5, [{"x": 1, "y": 2, "value": 3}]])
        assert a == b

    def test_key_changes_when_input_changes(self) -> None:
        a = cache_key("contours", ["L01", 5, [{"x": 1, "y": 2, "value": 3}]])
        b = cache_key("contours", ["L01", 5, [{"x": 1, "y": 2, "value": 4}]])
        assert a != b, "输入一变键就必须变,否则会拿到过期结果"

    def test_key_is_namespaced(self) -> None:
        assert cache_key("contours", [1]).startswith("geomine:cache:contours:")
        assert cache_key("section", [1]).startswith("geomine:cache:section:")


class TestCachedResult:
    async def test_second_call_hits_cache(self, fake_redis) -> None:
        calls = []

        def compute() -> dict:
            calls.append(1)
            return {"value": 42}

        first = await cached_result("contours", ["L01", 5], compute)
        second = await cached_result("contours", ["L01", 5], compute)

        assert first == second == {"value": 42}
        assert len(calls) == 1, "同一输入第二次应当命中缓存,不再计算"
        assert await fake_redis.ttl(cache_key("contours", ["L01", 5])) > 0

    async def test_concurrent_misses_compute_once(self, fake_redis) -> None:
        """缓存击穿:10 个并发请求同时未命中,只能有一个真算。"""
        calls = []

        def compute() -> dict:
            calls.append(1)
            # 模拟重计算(同步阻塞 → 走 to_thread)
            sum(range(200_000))
            return {"value": len(calls)}

        results = await asyncio.gather(
            *[cached_result("section", ["ax", 1], compute) for _ in range(10)]
        )

        assert len(calls) == 1, f"single-flight 应只计算一次,实际 {len(calls)} 次"
        assert all(result["value"] == 1 for result in results)

    async def test_lock_is_released_after_compute(self, fake_redis) -> None:
        await cached_result("contours", ["L01"], lambda: {"ok": True})
        assert await fake_redis.exists(lock_key(cache_key("contours", ["L01"]))) == 0, (
            "计算完必须释放锁,否则后续请求会一直等到超时"
        )

    async def test_lock_release_on_compute_error(self, fake_redis) -> None:
        def boom() -> dict:
            raise RuntimeError("算崩了")

        with pytest.raises(RuntimeError):
            await cached_result("contours", ["L02"], boom)

        assert await fake_redis.exists(lock_key(cache_key("contours", ["L02"]))) == 0

    async def test_waiter_computes_itself_when_lock_stuck(self, fake_redis) -> None:
        """锁被别的进程占着又不释放:不允许请求无限等待,超时后自己算。"""
        from app.services import analysis_cache

        await fake_redis.set(lock_key(cache_key("section", ["stuck"])), "1", px=10000)
        original = analysis_cache.WAIT_TIMEOUT_SECONDS
        analysis_cache.WAIT_TIMEOUT_SECONDS = 0.2
        try:
            calls = []

            def compute() -> dict:
                calls.append(1)
                return {"value": "自己算的"}

            result = await cached_result("section", ["stuck"], compute)
            assert result == {"value": "自己算的"}
            assert len(calls) == 1
        finally:
            analysis_cache.WAIT_TIMEOUT_SECONDS = original

    async def test_works_without_redis(self, monkeypatch) -> None:
        """Redis 不可用时退化为直接计算,不能 500。"""
        from app.core.config import settings

        redis_client.set_redis_for_tests(None)
        monkeypatch.setattr(settings, "redis_enabled", False)
        calls = []

        def compute() -> dict:
            calls.append(1)
            return {"value": "no-redis"}

        assert await cached_result("contours", ["L01"], compute) == {"value": "no-redis"}
        assert await cached_result("contours", ["L01"], compute) == {"value": "no-redis"}
        assert len(calls) == 2, "没有 Redis 时每次都算(无缓存但功能正常)"

    async def test_corrupted_cache_value_is_recomputed(self, fake_redis) -> None:
        key = cache_key("contours", ["L01", 5])
        await fake_redis.set(key, "{not json")
        result = await cached_result("contours", ["L01", 5], lambda: {"value": "重建"})
        assert result == {"value": "重建"}

    async def test_invalidate_namespace(self, fake_redis) -> None:
        await cached_result("contours", ["a"], lambda: {"v": 1})
        await cached_result("contours", ["b"], lambda: {"v": 2})
        await cached_result("section", ["c"], lambda: {"v": 3})

        removed = await invalidate_namespace("contours")

        assert removed == 2
        assert await fake_redis.exists(cache_key("section", ["c"])) == 1


class TestAnalysisEndpointsUseCache:
    async def test_contours_endpoint_is_cached(self, client, fake_redis, monkeypatch) -> None:
        import db_utils

        from app.api.v1 import analysis as analysis_api
        from app.core.database import AsyncSessionFactory

        await db_utils.open_or_skip()
        calls = []

        def fake_contours(samples, step=None):
            calls.append(len(samples))
            return {"levels": [1, 2], "segments": [], "step": step or 1.0}

        monkeypatch.setattr(analysis_api, "burial_depth_contours", fake_contours)

        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                for _ in range(2):
                    response = await client.get(
                        f"/api/v1/projects/{project.id}/analysis/contours",
                        params={"layer": "测试煤层"},
                    )
                    assert response.status_code == 200
                assert len(calls) == 1, "同一层位第二次请求应命中缓存"
            finally:
                await db_utils.drop_project(project.id)


class TestMetricsEndpoint:
    async def test_metrics_exposes_cache_and_job_metrics(self, client) -> None:
        response = await client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        body = response.text
        assert "geomine_analysis_cache_hits_total" in body
        assert "geomine_analysis_cache_misses_total" in body
        assert "geomine_modeling_job_duration_seconds" in body
        assert "geomine_modeling_job_results_total" in body
