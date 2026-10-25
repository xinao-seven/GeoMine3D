from __future__ import annotations

import shutil

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.modeling import ModelingJob
from app.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.common import PageMeta, PageResponse
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.modeling_service import collect_project_files

logger = get_logger("app.project")


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProjectRepository(session)

    async def list(self, *, page: int, page_size: int) -> PageResponse[ProjectRead]:
        projects = await self.repository.list(offset=(page - 1) * page_size, limit=page_size)
        total = await self.repository.count()
        return PageResponse(
            data=[ProjectRead.model_validate(item) for item in projects],
            meta=PageMeta(page=page, page_size=page_size, total=total),
        )

    async def get_or_404(self, project_id: str) -> Project:
        project = await self.repository.get(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)
        return project

    async def create(self, payload: ProjectCreate) -> Project:
        project = Project(**payload.model_dump())
        self.repository.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def update(self, project_id: str, payload: ProjectUpdate) -> Project:
        project = await self.get_or_404(project_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project_id: str) -> None:
        project = await self.get_or_404(project_id)
        job_ids = (
            await self.session.scalars(
                select(ModelingJob.id).where(ModelingJob.project_id == project_id)
            )
        ).all()
        await self.repository.delete(project)
        await self.session.commit()
        self._remove_job_files(project_id, job_ids)

    @staticmethod
    def _remove_job_files(project_id: str, job_ids: list[str]) -> None:
        """删除项目落库数据后,清理建模交付包与任务输入目录(失败仅记日志)。"""
        for path in collect_project_files(project_id, job_ids):
            target = settings.upload_path / path
            try:
                shutil.rmtree(target)
            except FileNotFoundError:
                continue
            except OSError as exc:
                logger.warning("清理建模文件目录失败 %s: %s", target, exc)
