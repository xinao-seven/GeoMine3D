"""建模任务端点：上传 Excel 建模(202)、任务详情/列表、队列水位与 SSE 实时进度。

路由层只保留 HTTP 关注点（multipart 解析、SSE 帧格式、断线续传头）；任务查询
在 ``modeling_service.ModelingService``，进度快照/事件流在 ``modeling_progress``。
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import DbSession
from app.models.modeling import ModelingJob
from app.schemas.common import DataResponse
from app.schemas.modeling import ModelingJobRead
from app.services.modeling_progress import (
    format_event,
    heartbeat_comment,
    is_terminal,
    read_events,
    read_progress,
)
from app.services.modeling_queue import queue_stats
from app.services.modeling_service import (
    ModelingService,
    dispatch_modeling_job,
    get_job_status,
)

router = APIRouter()
SSE_POLL_SECONDS = 0.4
SSE_PING_SECONDS = 15.0


async def _read_with_progress(job: ModelingJob) -> ModelingJobRead:
    """任务详情 + Redis 进度快照（轮询降级时前端也能拿到百分比）。"""
    data = ModelingJobRead.model_validate(job)
    if data.status == "completed":
        data.percent = 100.0
        return data
    snapshot = await read_progress(job.id)
    if snapshot is not None:
        data.percent = float(snapshot["percent"])
        if snapshot.get("stage"):
            data.stage = str(snapshot["stage"])
    return data


@router.post(
    "/modeling-jobs",
    response_model=DataResponse[ModelingJobRead],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_modeling_job(
    session: DbSession,
    name: Annotated[str, Form(min_length=1, max_length=120)],
    strata_file: Annotated[UploadFile, File(description="14层汇总长表 .xlsx")],
    location_file: Annotated[UploadFile, File(description="钻孔位置表 .xlsx")],
    description: Annotated[str | None, Form()] = None,
    grid_spacing_m: Annotated[float, Form(ge=10, le=1000)] = 100.0,
    boundary_padding_m: Annotated[float, Form(ge=0, le=10000)] = 200.0,
    pinchout_threshold_m: Annotated[float, Form(ge=0.0, le=10)] = 0.5,
    z_scale: Annotated[float, Form(ge=1, le=100)] = 20.0,
) -> DataResponse[ModelingJobRead]:
    """上传钻孔 Excel 创建独立项目并启动异步建模，立即返回任务信息（202）。

    投递方式对调用方透明：Redis 可用 → Stream 队列（可重试/可恢复/跨进程）；
    Redis 不可用 → 进程内后台任务。两者都是“立即返回 202 + 订阅进度”。
    """
    job = await ModelingService(session).create_job(
        name=name,
        description=description,
        strata_file=strata_file,
        location_file=location_file,
        params={
            "grid_spacing_m": grid_spacing_m,
            "boundary_padding_m": boundary_padding_m,
            "pinchout_threshold_m": pinchout_threshold_m,
            "z_scale": z_scale,
        },
    )
    await dispatch_modeling_job(job.id)
    return DataResponse(data=ModelingJobRead.model_validate(job))


@router.get("/modeling-queue", response_model=DataResponse[dict])
async def get_modeling_queue() -> DataResponse[dict]:
    """队列水位（积压/延迟/死信/未 ACK），供前端与运维看板使用。"""
    return DataResponse(data=await queue_stats())


@router.get("/modeling-jobs/{job_id}", response_model=DataResponse[ModelingJobRead])
async def get_modeling_job(job_id: str, session: DbSession) -> DataResponse[ModelingJobRead]:
    """任务详情（附当前进度百分比，SSE 不可用时的轮询降级数据源）。"""
    service = ModelingService(session)
    return DataResponse(data=await _read_with_progress(await service.get_job_or_404(job_id)))


@router.get("/modeling-jobs/{job_id}/events")
async def stream_modeling_job(
    job_id: str,
    session: DbSession,
    request: Request,
) -> StreamingResponse:
    """SSE 实时进度。

    - 首帧推当前快照，晚连进来的页面也能立即看到百分比；
    - 重连时浏览器自动带 ``Last-Event-ID``，从那条事件之后 ``XRANGE`` 补发，
      断线期间产生的进度不会丢（这是选 Stream 而不是 Pub/Sub 的原因）；
    - 任务进入终态后补一帧 ``event: done`` 并关闭连接，前端不必再自己猜。
    """
    # 404 提前拦截，避免对不存在的任务开长连接
    await ModelingService(session).get_job_or_404(job_id)
    last_event_id = request.headers.get("last-event-id") or request.query_params.get("last_id")

    async def _stream() -> AsyncIterator[str]:
        """SSE 帧生成器：补发事件 → 终态 done 帧 → keep-alive，循环到断开。"""
        # 首次连接(没有 Last-Event-ID)先推当前快照,晚进来的页面也能立刻看到进度;
        # 重连时不推快照,否则会与随后补发的事件重复。
        if last_event_id is None:
            snapshot = await read_progress(job_id)
            if snapshot is not None:
                yield format_event(("0-0", snapshot))
        cursor = last_event_id
        last_ping = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            events = await read_events(job_id, cursor)
            for entry in events:
                cursor = entry[0]
                yield format_event(entry)
            if events:
                last_ping = time.monotonic()
            else:
                current = await get_job_status(job_id)
                if current is None or is_terminal(current):
                    final = {
                        "stage": "完成" if current == "completed" else "结束",
                        "percent": 100.0,
                        "message": "建模完成" if current == "completed" else "任务已结束",
                    }
                    yield format_event((cursor or "0-0", final), event="done")
                    return
                if time.monotonic() - last_ping >= SSE_PING_SECONDS:
                    last_ping = time.monotonic()
                    yield heartbeat_comment()
                await asyncio.sleep(SSE_POLL_SECONDS)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # 告诉 nginx 不要缓冲 SSE 帧
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/projects/{project_id}/modeling-jobs",
    response_model=DataResponse[list[ModelingJobRead]],
)
async def list_modeling_jobs(
    project_id: str, session: DbSession
) -> DataResponse[list[ModelingJobRead]]:
    """项目的历史建模任务（附当前进度；前端项目卡片用它画进度条）。"""
    jobs = await ModelingService(session).list_project_jobs(project_id)
    return DataResponse(data=[await _read_with_progress(job) for job in jobs])
