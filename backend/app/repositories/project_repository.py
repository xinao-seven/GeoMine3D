from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, *, offset: int, limit: int) -> list[Project]:
        result = await self.session.scalars(
            select(Project).order_by(Project.updated_at.desc()).offset(offset).limit(limit)
        )
        return list(result)

    async def count(self) -> int:
        return int(await self.session.scalar(select(func.count(Project.id))) or 0)

    async def get(self, project_id: str) -> Project | None:
        return await self.session.get(Project, project_id)

    def add(self, project: Project) -> None:
        self.session.add(project)

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
