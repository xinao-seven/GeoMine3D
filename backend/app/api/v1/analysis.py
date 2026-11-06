"""项目分析端点：概览 / 虚拟钻孔 / 资源量 / 等值线 / 勘探线剖面。

路由层只做三件事：校验项目存在、按「真实输入」组装分析缓存键
（``analysis_cache.cached_result``）、把 service 的纯函数结果包成统一响应。
数据取数在 ``analysis_service`` 的 fetch/load 函数里，数值计算全部是纯函数。
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.dependencies import DbSession
from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.common import DataResponse
from app.services.analysis_cache import cached_result
from app.services.analysis_service import (
    build_overview,
    burial_depth_contours,
    estimate_workingface_reserves,
    fetch_borehole_data,
    load_overview_inputs,
    load_section_context,
    virtual_borehole,
)
from app.services.boundary_service import read_polylines
from app.services.section_service import compute_section, resolve_layer_files
from app.services.workspace_service import ensure_project

router = APIRouter()


class VirtualBoreholeRequest(BaseModel):
    """虚拟钻孔查询点（矿区投影坐标，米）。"""

    x: float = Field(description="查询点东向投影坐标(米)")
    y: float = Field(description="查询点北向投影坐标(米)")
    max_neighbors: int = Field(default=8, ge=1, le=32)


class SectionRequest(BaseModel):
    """勘探线剖面两端点（矿区投影坐标，米）。"""

    ax: float = Field(description="剖面线端点A东向投影坐标(米)")
    ay: float = Field(description="剖面线端点A北向投影坐标(米)")
    bx: float = Field(description="剖面线端点B东向投影坐标(米)")
    by: float = Field(description="剖面线端点B北向投影坐标(米)")


@router.get(
    "/projects/{project_id}/analysis/overview",
    response_model=DataResponse[dict],
)
async def get_analysis_overview(project_id: str, session: DbSession):
    """项目统计概览：钻孔/地层/模型/工作面汇总与分布数据。"""
    await ensure_project(session, project_id)
    boreholes, segments, faces, model_count = await load_overview_inputs(session, project_id)
    overview = build_overview(boreholes, segments, faces, model_count)
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

    # 缓存键直接用“真实输入”，钻孔一变键就变；不需要猜 TTL。
    result = dict(
        await cached_result(
            "virtual_borehole",
            [project_id, boreholes, segments_by_borehole, payload.x, payload.y,
             payload.max_neighbors],
            lambda: virtual_borehole(
                boreholes, segments_by_borehole, payload.x, payload.y, payload.max_neighbors
            ),
        )
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

    # 等值线只依赖“样本点 + 步长”，所以用它们当缓存键：换数据自然失效。
    result = dict(
        await cached_result(
            "contours",
            [layer.strip(), step, samples],
            lambda: burial_depth_contours(samples, step=step),
        )
    )
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
    project, layer_rows, dataset = await load_section_context(session, project_id)
    layers = resolve_layer_files(layer_rows)
    if not layers:
        raise AppError("SECTION_NO_LAYER_MODELS", "项目缺少分层模型，无法生成剖面", status_code=400)

    origin = {"x": project.origin_x, "y": project.origin_y, "z": project.origin_z}
    result = await cached_result(
        "section",
        [dataset, origin, payload.ax, payload.ay, payload.bx, payload.by],
        lambda: compute_section(layers, payload.ax, payload.ay, payload.bx, payload.by, origin),
    )
    return DataResponse(data=result)
