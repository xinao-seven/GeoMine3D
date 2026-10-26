from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.dependencies import DbSession
from app.core.config import settings
from app.core.exceptions import AppError
from app.models.asset import ModelAsset, ModelVersion
from app.models.borehole import Borehole, BoreholeSegment
from app.models.project import Project
from app.models.workspace import WorkingFace
from app.schemas.common import DataResponse
from app.services.analysis_service import (
    burial_depth_contours,
    build_overview,
    estimate_workingface_reserves,
    virtual_borehole,
)
from app.services.boundary_service import read_polylines
from app.services.section_service import compute_section, resolve_layer_files
from app.services.workspace_service import ensure_project


router = APIRouter()


class VirtualBoreholeRequest(BaseModel):
    x: float = Field(description="查询点东向投影坐标(米)")
    y: float = Field(description="查询点北向投影坐标(米)")
    max_neighbors: int = Field(default=8, ge=1, le=32)


class SectionRequest(BaseModel):
    ax: float = Field(description="剖面线端点A东向投影坐标(米)")
    ay: float = Field(description="剖面线端点A北向投影坐标(米)")
    bx: float = Field(description="剖面线端点B东向投影坐标(米)")
    by: float = Field(description="剖面线端点B北向投影坐标(米)")


async def fetch_borehole_data(session: DbSession, project_id: str):
    """取项目钻孔与分层，返回 (钻孔列表, 按钻孔分组的分层, 平铺分层)。"""
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

    segments_by_borehole: dict[str, list[dict]] = {}
    flat_segments: list[dict] = []
    for seg in segment_rows:
        item = {
            "borehole_id": seg.borehole_id,
            "layer_name": seg.layer_name,
            "top_depth": seg.top_depth,
            "bottom_depth": seg.bottom_depth,
            "thickness": seg.thickness,
            "color": seg.color,
        }
        segments_by_borehole.setdefault(seg.borehole_id, []).append(item)
        flat_segments.append(item)

    boreholes = [
        {"id": b.id, "code": b.code, "name": b.name, "x": b.x, "y": b.y, "total_depth": b.total_depth}
        for b in borehole_rows
    ]
    return boreholes, segments_by_borehole, flat_segments


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

    boreholes, segments_by_borehole, _ = await fetch_borehole_data(session, project_id)

    result = virtual_borehole(
        boreholes, segments_by_borehole, payload.x, payload.y, payload.max_neighbors
    )
    result["x"] = payload.x
    result["y"] = payload.y
    return DataResponse(data=result)


@router.get("/projects/{project_id}/analysis/reserves", response_model=DataResponse[dict])
async def get_workingface_reserves(
    project_id: str,
    session: DbSession,
    density: float = 1.35,
):
    """工作面煤炭资源量估算：shp 圈闭面积 × 圈闭内钻孔煤层平均厚度 × 密度。"""
    await ensure_project(session, project_id)
    boreholes, segments_by_borehole, _ = await fetch_borehole_data(session, project_id)
    face_polygons = read_polylines(settings.workingface_boundary_shp)
    items = estimate_workingface_reserves(
        face_polygons, boreholes, segments_by_borehole, density_t_per_m3=density
    )
    total = sum(item["reserve_wan_t"] or 0 for item in items)
    return DataResponse(
        data={
            "items": items,
            "density_t_m3": density,
            "face_count": len(items),
            "total_reserve_wan_t": round(total, 1),
        }
    )


@router.get("/projects/{project_id}/analysis/contours", response_model=DataResponse[dict])
async def get_layer_contours(
    project_id: str,
    session: DbSession,
    layer: str,
    step: float | None = None,
):
    """某地层顶板埋深等值线：钻孔 IDW 网格 + Marching Squares（投影坐标）。"""
    await ensure_project(session, project_id)
    boreholes, segments_by_borehole, _ = await fetch_borehole_data(session, project_id)

    samples = []
    for borehole in boreholes:
        for seg in segments_by_borehole.get(borehole["id"], []):
            if seg["layer_name"].strip() == layer.strip():
                samples.append({"x": borehole["x"], "y": borehole["y"], "value": seg["top_depth"]})
                break

    result = burial_depth_contours(samples, step=step)
    result["layer"] = layer
    result["sample_count"] = len(samples)
    return DataResponse(data=result)


@router.post(
    "/projects/{project_id}/analysis/section",
    response_model=DataResponse[dict],
)
async def create_section_profile(
    project_id: str, payload: SectionRequest, session: DbSession
):
    """勘探线剖面：剖线 × 分层 GLB 闭合壳求交，返回逐层 (沿线距离, 标高) 矢量剖面。"""
    project = await session.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)

    rows = (
        await session.execute(
            select(
                ModelAsset.name,
                ModelAsset.metadata_json,
                ModelVersion.storage_scope,
                ModelVersion.file_path,
            )
            .join(ModelVersion, ModelVersion.id == ModelAsset.current_version_id)
            .where(ModelAsset.project_id == project_id, ModelAsset.model_type == "stratum")
        )
    ).all()
    layer_rows = [
        (row.name, row.metadata_json or {}, row.storage_scope, row.file_path) for row in rows
    ]
    layers = resolve_layer_files(layer_rows)
    if not layers:
        raise AppError("SECTION_NO_LAYER_MODELS", "项目缺少分层模型，无法生成剖面", status_code=400)

    result = compute_section(
        layers,
        payload.ax,
        payload.ay,
        payload.bx,
        payload.by,
        {"x": project.origin_x, "y": project.origin_y, "z": project.origin_z},
    )
    return DataResponse(data=result)
