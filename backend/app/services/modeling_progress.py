"""建模进度:引擎结构化埋点 → Redis 快照 → SSE 推送。

数据流::

    引擎子进程 stdout  [progress] {"stage":..,"percent":..,"message":..}
      │  (app/services/modeling_service.py::_pump_stdout 逐行解析)
      ├─▶ Redis Hash  <p>:modeling:progress:<job_id>      当前快照(新连接立刻能拿到)
      └─▶ Redis Stream <p>:modeling:progress:stream:<job_id>  历史事件(断线续传用)
                                    │
                     GET /api/v1/modeling-jobs/{id}/events  (SSE)
                                    │  浏览器自动带 Last-Event-ID 重连
                                    ▼
                             前端进度条

为什么用 Stream + ``XRANGE`` 而不是 Pub/Sub:
pub/sub 是"发出去就不管",订阅者在断线的那几秒会永久丢掉事件,而且“读快照 → 订阅”
之间有窗口期,可能漏掉中间态;Stream 有 id,``Last-Event-ID`` 天然对应 stream entry
id,重连时从上次的 id 往后 ``XRANGE`` 就能把漏掉的帧补齐。代价是每个连接轮询,但
一个建模任务只有几十帧、单用户场景,代价可以忽略。
"""
from __future__ import annotations

import json
from typing import Any

from app.core.redis_client import get_redis, keys

PROGRESS_TTL_SECONDS = 86400
STREAM_MAXLEN = 500
TERMINAL_STATUSES = ("completed", "failed")


def snapshot_key(job_id: str) -> str:
    return keys("modeling", "progress", job_id)


def stream_key(job_id: str) -> str:
    return keys("modeling", "progress", "stream", job_id)


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    percent = payload.get("percent", 0)
    try:
        value = float(percent)
    except (TypeError, ValueError):
        value = 0.0
    # message 可能是多行引擎输出/异常堆栈,压成单行避免把 SSE 帧撕断。
    message = str(payload.get("message") or "").replace("\r", " ").replace("\n", " ")
    return {
        "stage": str(payload.get("stage") or ""),
        "percent": max(0.0, min(100.0, value)),
        "message": message,
    }


async def record_progress(job_id: str, stage: str, percent: float, message: str) -> str | None:
    """写一份进度快照 + 追加一条事件。Redis 不可用时静默返回 None(不影响建模)。"""
    redis = await get_redis()
    if redis is None:
        return None
    data = _normalize({"stage": stage, "percent": percent, "message": message})
    try:
        pipe = redis.pipeline()
        pipe.hset(snapshot_key(job_id), mapping=data)
        pipe.expire(snapshot_key(job_id), PROGRESS_TTL_SECONDS)
        pipe.xadd(
            stream_key(job_id),
            data,
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        pipe.expire(stream_key(job_id), PROGRESS_TTL_SECONDS)
        results = await pipe.execute()
    except Exception:  # noqa: BLE001 - 进度是展示层,不能因为它失败而中断建模
        return None
    entry_id = results[-2]
    return str(entry_id) if entry_id is not None else None


async def read_progress(job_id: str) -> dict[str, Any] | None:
    """读当前进度快照(SSE 首帧与轮询降级都用它)。"""
    redis = await get_redis()
    if redis is None:
        return None
    try:
        data = await redis.hgetall(snapshot_key(job_id))
    except Exception:  # noqa: BLE001
        return None
    if not data:
        return None
    return _normalize(data)


async def read_events(
    job_id: str, last_id: str | None = None, count: int = 50
) -> list[tuple[str, dict[str, Any]]]:
    """读 ``last_id`` 之后的事件(``None`` 表示从头读)。断线续传就靠它。"""
    redis = await get_redis()
    if redis is None:
        return []
    start = last_id or "-"
    if last_id is None:
        # 首帧不需要全部历史,给最近一帧即可(更早的已被快照覆盖)。
        entries = await redis.xrevrange(stream_key(job_id), max="+", min="-", count=1)
        entries = list(reversed(entries))
    else:
        # XRANGE 的 (id 表示"不包含该 id";没有 id 时用 "-" 表示从头。
        entries = await redis.xrange(stream_key(job_id), min=f"({start}", max="+", count=count)
    return [(str(entry_id), _normalize(fields)) for entry_id, fields in entries]


def json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def format_event(entry: tuple[str, dict[str, Any]], *, event: str = "progress") -> str:
    """把一条进度事件渲染成 SSE 帧(``id:``/``event:``/``data:``)。"""
    entry_id, data = entry
    return f"id: {entry_id}\nevent: {event}\ndata: {json_dumps(data)}\n\n"


async def final_progress(job: Any) -> dict[str, Any]:
    """任务收尾时补最后一帧:100% 完成 / 失败原因。"""
    status = str(getattr(job, "status", ""))
    if status == "completed":
        return {
            "stage": "完成",
            "percent": 100.0,
            "message": getattr(job, "message", "") or "建模完成",
        }
    return {
        "stage": "失败",
        "percent": 100.0,
        "message": (getattr(job, "error_message", None) or "建模失败")[:500],
    }


def is_terminal(status: str | None) -> bool:
    return str(status) in TERMINAL_STATUSES


def heartbeat_comment() -> str:
    """SSE 注释行:每 15s 发一次,防止代理/浏览器把空闲连接掐掉。"""
    return ": keep-alive\n\n"
