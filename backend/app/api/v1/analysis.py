from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.dependencies import DbSession
from app.models.asset import ModelAsset
from app.models.borehole import Borehole, BoreholeSegment
from app.models.workspace import WorkingFace
from app.schemas.common import DataResponse
from app.services.analysis_service import build_overview, virtual_borehole
from app.services.workspace_service import ensure_project


router = APIRouter()


class VirtualBoreholeRequest(BaseModel):
    x: float = Field(description="查询点东向投影坐标(米)")
    y: float = Field(description="查询点北向投影坐标(米)")
    max_neighbors: int = Field(default=8, ge=1, le=32)


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


@router.post(
    "/projects/{project_id}/analysis/virtual-borehole",
    response_model=DataResponse[dict],
)
async def create_virtual_borehole(
    project_id: str, payload: VirtualBoreholeRequest, session: DbSession
):
    """任意点虚拟钻孔：按邻近钻孔 IDW 插值各地层顶底埋深。"""
    await ensure_project(session, project_id)

    borehole_rows = (
        await session.scalars(
            select(Borehole).where(Borehole.project_id == project_id)
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

    segments_by_borehole: dict[str, list[dict]] = {}
    for seg in segment_rows:
        segments_by_borehole.setdefault(seg.borehole_id, []).append(
            {
                "layer_name": seg.layer_name,
                "top_depth": seg.top_depth,
                "bottom_depth": seg.bottom_depth,
                "thickness": seg.thickness,
                "color": seg.color,
            }
        )
    boreholes = [{"id": b.id, "code": b.code, "x": b.x, "y": b.y} for b in borehole_rows]

    result = virtual_borehole(
        boreholes, segments_by_borehole, payload.x, payload.y, payload.max_neighbors
    )
    result["x"] = payload.x
    result["y"] = payload.y
    return DataResponse(data=result)
