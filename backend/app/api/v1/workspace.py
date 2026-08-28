from fastapi import APIRouter
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.models.workspace import ImportRun, WorkingFace
from app.schemas.common import DataResponse
from app.schemas.workspace import ImportRunRead, WorkingFaceRead
from app.services.workspace_service import ensure_project


router = APIRouter()


@router.get(
    "/projects/{project_id}/working-faces",
    response_model=DataResponse[list[WorkingFaceRead]],
)
async def list_working_faces(project_id: str, session: DbSession):
    await ensure_project(session, project_id)
    rows = await session.scalars(
        select(WorkingFace)
        .where(WorkingFace.project_id == project_id)
        .order_by(WorkingFace.code)
    )
    return DataResponse(data=list(rows))


@router.get(
    "/projects/{project_id}/imports",
    response_model=DataResponse[list[ImportRunRead]],
)
async def list_import_runs(project_id: str, session: DbSession):
    await ensure_project(session, project_id)
    rows = await session.scalars(
        select(ImportRun)
        .where(ImportRun.project_id == project_id)
        .order_by(ImportRun.created_at.desc())
    )
    return DataResponse(data=list(rows))
