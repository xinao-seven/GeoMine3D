"""标注持久化服务。

三维工作台里的测量/文字标注按项目存库（``annotations`` 表），前端在项目模式下
自动保存/恢复；本模块只承载 CRUD，几何语义（位置、颜色）由前端解释。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.scene import Annotation
from app.schemas.annotation import AnnotationCreate
from app.services.workspace_service import ensure_project


class AnnotationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, project_id: str) -> list[Annotation]:
        """按创建时间返回项目的全部标注（前端按此顺序恢复场景）。"""
        await ensure_project(self.session, project_id)
        rows = await self.session.scalars(
            select(Annotation)
            .where(Annotation.project_id == project_id)
            .order_by(Annotation.created_at)
        )
        return list(rows)

    async def create(self, project_id: str, payload: AnnotationCreate) -> Annotation:
        await ensure_project(self.session, project_id)
        annotation = Annotation(project_id=project_id, **payload.model_dump())
        self.session.add(annotation)
        await self.session.commit()
        await self.session.refresh(annotation)
        return annotation

    async def delete(self, annotation_id: str) -> None:
        annotation = await self.session.get(Annotation, annotation_id)
        if annotation is None:
            raise AppError("ANNOTATION_NOT_FOUND", "标注不存在", status_code=404)
        await self.session.delete(annotation)
        await self.session.commit()
