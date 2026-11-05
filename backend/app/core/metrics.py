"""Prometheus 指标(轻量,只收真正会用来看板的几个)。

不引 opentelemetry:跨进程 trace 成本高、演示也看不见;而这几类计数/直方图能直接
回答运维最常问的三个问题 —— 缓存有没有用、建模任务多久、失败率高不高。
"""
from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

CACHE_HITS = Counter(
    "geomine_analysis_cache_hits_total",
    "分析结果缓存命中次数",
    ["namespace"],
)
CACHE_MISSES = Counter(
    "geomine_analysis_cache_misses_total",
    "分析结果缓存未命中次数",
    ["namespace", "reason"],
)
CACHE_SHARED = Counter(
    "geomine_analysis_cache_shared_total",
    "靠 single-flight 等到别人算完的次数(避免重复计算的量)",
    ["namespace"],
)

MODELING_JOB_DURATION = Histogram(
    "geomine_modeling_job_duration_seconds",
    "建模任务执行时长(秒)",
    buckets=(5, 15, 30, 60, 120, 300, 600, 1800),
)
MODELING_JOB_RESULTS = Counter(
    "geomine_modeling_job_results_total",
    "建模任务结束状态计数",
    ["status"],
)


def record_cache_hit(namespace: str) -> None:
    CACHE_HITS.labels(namespace=namespace).inc()


def record_cache_miss(namespace: str, reason: str = "miss") -> None:
    CACHE_MISSES.labels(namespace=namespace, reason=reason).inc()


def record_cache_shared(namespace: str) -> None:
    CACHE_SHARED.labels(namespace=namespace).inc()


def record_job_result(status: str, duration_seconds: float | None = None) -> None:
    MODELING_JOB_RESULTS.labels(status=status).inc()
    if duration_seconds is not None:
        MODELING_JOB_DURATION.observe(max(0.0, duration_seconds))


def render_metrics() -> tuple[bytes, str]:
    """给 ``GET /metrics`` 用。"""
    return generate_latest(), CONTENT_TYPE_LATEST
