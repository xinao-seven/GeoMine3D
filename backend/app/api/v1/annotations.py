from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.core.exceptions import AppError
from app.models.scene import Annotation
from app.schemas.annotation import AnnotationCreate, AnnotationRead
from app.schemas.common import DataResponse
from app.services.workspace_service import ensure_project


router = APIRouter()


@router.get(
    "/projects/{project_id}/annotations",
    response_model=DataResponse[list[AnnotationRead]],
)
async def list_annotations(project_id: str, session: DbSession):
    await ensure_project(session, project_id)
    rows = await session.scalars(
        select(Annotation)
        .where(Annotation.project_id == project_id)
        .order_by(Annotation.created_at)
    )
    return DataResponse(data=list(rows))


@router.post(
    "/projects/{project_id}/annotations",
    response_model=DataResponse[AnnotationRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    project_id: str, payload: AnnotationCreate, session: DbSession
):
    await ensure_project(session, project_id)
    annotation = Annotation(
        project_id=project_id,
        title=payload.title,
        content=payload.content,
        position_x=payload.position_x,
        position_y=payload.position_y,
        position_z=payload.position_z,
        color=payload.color,
    )
    session.add(annotation)
    await session.commit()
    await session.refresh(annotation)
    return DataResponse(data=annotation)


@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_annotation(annotation_id: str, session: DbSession):
    annotation = await session.get(Annotation, annotation_id)
    if annotation is None:
        raise AppError("ANNOTATION_NOT_FOUND", "标注不存在", status_code=404)
    await session.delete(annotation)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
