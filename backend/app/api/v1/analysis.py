from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.dependencies import DbSession
from app.models.asset import ModelAsset
from app.models.borehole import Borehole, BoreholeSegment
from app.models.workspace import WorkingFace
from app.schemas.common import DataResponse
from app.services.analysis_service import build_overview
from app.services.workspace_service import ensure_project


router = APIRouter()


@router.get(
    "/projects/{project_id}/analysis/overview",
    response_model=DataResponse[dict],
)
async def get_analysis_overview(project_id: str, session: DbSession):
    """项目统计概览：钻孔/地层/模型/工作面汇总与分布数据。"""
    await ensure_project(session, project_id)

    borehole_rows = (
        await session.scalars(
            select(Borehole).where(Borehole.project_id == project_id).order_by(Borehole.code)
        )
    ).all()
    segment_rows = (
        await session.scalars(
            select(BoreholeSegment)
            .join(Borehole, BoreholeSegment.borehole_id == Borehole.id)
            .where(Borehole.project_id == project_id)
            .order_by(BoreholeSegment.top_depth)
        )
    ).all()
    face_rows = (
        await session.scalars(
            select(WorkingFace).where(WorkingFace.project_id == project_id).order_by(WorkingFace.code)
        )
    ).all()
    model_count = await session.scalar(
        select(func.count()).select_from(ModelAsset).where(ModelAsset.project_id == project_id)
    )

    segments = [
        {
            "borehole_id": seg.borehole_id,
            "layer_name": seg.layer_name,
            "top_depth": seg.top_depth,
            "bottom_depth": seg.bottom_depth,
            "thickness": seg.thickness,
        }
        for seg in segment_rows
    ]
    faces = [
        {
            "code": face.code,
            "name": face.name,
            "status": face.status,
            "length": face.length,
            "width": face.width,
        }
        for face in face_rows
    ]
    boreholes = [
        {
            "code": b.code,
            "name": b.name,
            "total_depth": b.total_depth,
        }
        for b in borehole_rows
    ]

    overview = build_overview(boreholes, segments, faces, model_count or 0)
    return DataResponse(data=overview)
