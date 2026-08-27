from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import DbSession
from app.schemas.common import DataResponse, PageResponse
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService


router = APIRouter()


@router.get("", response_model=PageResponse[ProjectRead])
async def list_projects(
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PageResponse[ProjectRead]:
    return await ProjectService(session).list(page=page, page_size=page_size)


@router.post("", response_model=DataResponse[ProjectRead], status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, session: DbSession) -> DataResponse[ProjectRead]:
    project = await ProjectService(session).create(payload)
    return DataResponse(data=project)


@router.get("/{project_id}", response_model=DataResponse[ProjectRead])
async def get_project(project_id: str, session: DbSession) -> DataResponse[ProjectRead]:
    project = await ProjectService(session).get_or_404(project_id)
    return DataResponse(data=project)


@router.patch("/{project_id}", response_model=DataResponse[ProjectRead])
async def update_project(
    project_id: str, payload: ProjectUpdate, session: DbSession
) -> DataResponse[ProjectRead]:
    project = await ProjectService(session).update(project_id, payload)
    return DataResponse(data=project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, session: DbSession) -> Response:
    await ProjectService(session).delete(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
