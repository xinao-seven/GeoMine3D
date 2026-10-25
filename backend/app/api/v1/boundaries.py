from fastapi import APIRouter

from app.api.dependencies import DbSession
from app.schemas.common import DataResponse
from app.services.boundary_service import load_boundaries
from app.services.workspace_service import ensure_project


router = APIRouter()


@router.get("/projects/{project_id}/boundaries", response_model=DataResponse[dict])
async def get_boundaries(project_id: str, session: DbSession):
    """矿区井田边界与开采工作面范围折线（投影坐标，米）。"""
    await ensure_project(session, project_id)
    return DataResponse(data=load_boundaries())
