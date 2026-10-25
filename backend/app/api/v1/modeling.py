from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.core.exceptions import AppError
from app.models.modeling import ModelingJob
from app.schemas.common import DataResponse
from app.schemas.modeling import ModelingJobRead
from app.services.modeling_service import ModelingService, spawn_modeling_job
from app.services.workspace_service import ensure_project


router = APIRouter()


async def _get_job_or_404(session, job_id: str) -> ModelingJob:
    job = (
        await session.scalars(select(ModelingJob).where(ModelingJob.id == job_id))
    ).first()
    if job is None:
        raise AppError("MODELING_JOB_NOT_FOUND", "建模任务不存在", status_code=404)
    return job


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
    """上传钻孔 Excel 创建独立项目并启动异步建模,立即返回任务信息(202)。"""
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
    spawn_modeling_job(job.id)
    return DataResponse(data=ModelingJobRead.model_validate(job))


@router.get("/modeling-jobs/{job_id}", response_model=DataResponse[ModelingJobRead])
async def get_modeling_job(job_id: str, session: DbSession) -> DataResponse[ModelingJobRead]:
    return DataResponse(data=ModelingJobRead.model_validate(await _get_job_or_404(session, job_id)))


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
    return DataResponse(data=[ModelingJobRead.model_validate(job) for job in jobs])
