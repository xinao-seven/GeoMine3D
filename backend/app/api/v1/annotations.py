"""标注端点：项目级标注的列表 / 新增 / 单条删除（前端自动保存/恢复）。"""

from fastapi import APIRouter, Response, status

from app.api.dependencies import DbSession
from app.schemas.annotation import AnnotationCreate, AnnotationRead
from app.schemas.common import DataResponse
from app.services.annotation_service import AnnotationService

router = APIRouter()


@router.get(
    "/projects/{project_id}/annotations",
    response_model=DataResponse[list[AnnotationRead]],
)
async def list_annotations(project_id: str, session: DbSession):
    """列出项目全部标注（按创建时间升序，与前端恢复顺序一致）。"""
    return DataResponse(data=await AnnotationService(session).list(project_id))


@router.post(
    "/projects/{project_id}/annotations",
    response_model=DataResponse[AnnotationRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    project_id: str, payload: AnnotationCreate, session: DbSession
):
    """新增一条标注（工作台保存场景时逐条调用）。"""
    return DataResponse(data=await AnnotationService(session).create(project_id, payload))


@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_annotation(annotation_id: str, session: DbSession):
    """删除单条标注（支持工作台里的“单条删除”与 CSV 导出前的清理）。"""
    await AnnotationService(session).delete(annotation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
