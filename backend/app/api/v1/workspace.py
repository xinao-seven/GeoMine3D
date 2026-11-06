"""工作台辅助端点：工作面列表与导入历史。"""

from fastapi import APIRouter

from app.api.dependencies import DbSession
from app.schemas.common import DataResponse
from app.schemas.workspace import ImportRunRead, WorkingFaceRead
from app.services import workspace_service

router = APIRouter()


@router.get(
    "/projects/{project_id}/working-faces",
    response_model=DataResponse[list[WorkingFaceRead]],
)
async def list_working_faces(project_id: str, session: DbSession):
    """项目工作面列表（资源树“工作面”分组数据源）。"""
    return DataResponse(data=await workspace_service.list_working_faces(session, project_id))


@router.get(
    "/projects/{project_id}/imports",
    response_model=DataResponse[list[ImportRunRead]],
)
async def list_import_runs(project_id: str, session: DbSession):
    """项目导入历史（最近一次导入的来源/状态/摘要）。"""
    return DataResponse(data=await workspace_service.list_import_runs(session, project_id))
