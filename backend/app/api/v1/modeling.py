import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.core.database import AsyncSessionFactory
from app.core.exceptions import AppError
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
from app.services.modeling_service import ModelingService, dispatch_modeling_job
from app.services.workspace_service import ensure_project

router = APIRouter()
SSE_POLL_SECONDS = 0.4
SSE_PING_SECONDS = 15.0


async def _get_job_or_404(session, job_id: str) -> ModelingJob:
    job = (
        await session.scalars(select(ModelingJob).where(ModelingJob.id == job_id))
    ).first()
    if job is None:
        raise AppError("MODELING_JOB_NOT_FOUND", "建模任务不存在", status_code=404)
    return job


async def _read_with_progress(job: ModelingJob) -> ModelingJobRead:
    """任务详情 + Redis 进度快照(轮询降级时前端也能拿到百分比)。"""
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


async def _job_status(job_id: str) -> str | None:
    """开新会话查一次状态:

    SSE 是长连接,不能一直拿着请求级会话(会长期占着事务/连接);而且 MySQL 默认
    REPEATABLE READ,同一事务里反复读会永远看不到 worker 提交的新状态。
    """
    async with AsyncSessionFactory() as session:
        job = await session.get(ModelingJob, job_id)
        return None if job is None else job.status


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
    """上传钻孔 Excel 创建独立项目并启动异步建模,立即返回任务信息(202)。

    投递方式对调用方透明:Redis 可用 → Stream 队列(可重试/可恢复/跨进程);
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
    """队列水位(积压/延迟/死信/未 ACK),供前端与运维看板使用。"""
    return DataResponse(data=await queue_stats())


@router.get("/modeling-jobs/{job_id}", response_model=DataResponse[ModelingJobRead])
async def get_modeling_job(job_id: str, session: DbSession) -> DataResponse[ModelingJobRead]:
    return DataResponse(data=await _read_with_progress(await _get_job_or_404(session, job_id)))


@router.get("/modeling-jobs/{job_id}/events")
async def stream_modeling_job(
    job_id: str,
    session: DbSession,
    request: Request,
) -> StreamingResponse:
    """SSE 实时进度。

    - 首帧推当前快照,晚连进来的页面也能立即看到百分比;
    - 重连时浏览器自动带 ``Last-Event-ID``,从那条事件之后 ``XRANGE`` 补发,
      断线期间产生的进度不会丢(这是选 Stream 而不是 Pub/Sub 的原因);
    - 任务进入终态后补一帧 ``event: done`` 并关闭连接,前端不必再自己猜。
    """
    await _get_job_or_404(session, job_id)  # 404 提前拦截,避免对不存在的任务开长连接
    last_event_id = request.headers.get("last-event-id") or request.query_params.get("last_id")

    async def _stream() -> AsyncIterator[str]:
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
                current = await _job_status(job_id)
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
    await ensure_project(session, project_id)
    jobs = await session.scalars(
        select(ModelingJob)
        .where(ModelingJob.project_id == project_id)
        .order_by(ModelingJob.created_at.desc())
    )
    return DataResponse(data=[await _read_with_progress(job) for job in jobs])
