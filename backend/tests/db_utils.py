"""数据库相关单测的共享工具(建/删临时项目与任务行)。

约定:
- MySQL 不可用时用例 ``pytest.skip``,保证没起 docker compose 的机器上仍能跑
  纯文件系统/Redis 用例;
- 每个用例自建临时项目并在 finally 里删掉,不污染开发库;
- open_or_skip 顺手清掉上次异常运行遗留的临时项目(进程被强杀/库缺表导致
  finally 没跑完时,self-heal 保证套件在脏库上可重复执行)。
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionFactory
from app.models.asset import ModelAsset
from app.models.modeling import ModelingJob
from app.models.project import Project

# 单测临时项目的命名前缀(见 create_project 与 test_modeling_register),
# 兜底清理按它匹配;真实业务项目不应使用该前缀。
STALE_TEST_PROJECT_PREFIX = "单测-"


async def open_or_skip() -> None:
    """探活;连不上 MySQL 就跳过依赖数据库的用例,顺带清理上次遗留的临时项目。"""
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
            await _drop_stale_test_projects(session)
    except Exception as exc:  # noqa: BLE001 - 任何连接问题都按"不可用"处理
        pytest.skip(f"MySQL 不可用,跳过数据库用例: {exc}")


async def _drop_stale_test_projects(session: AsyncSession) -> None:
    """删除上次异常运行遗留的 ``单测-*`` 项目(正常路径每用例 finally 已删)。"""
    await session.execute(
        text(
            "UPDATE model_assets SET current_version_id = NULL "
            f"WHERE project_id IN (SELECT id FROM projects WHERE name LIKE '{STALE_TEST_PROJECT_PREFIX}%')"
        )
    )
    await session.execute(
        text(f"DELETE FROM projects WHERE name LIKE '{STALE_TEST_PROJECT_PREFIX}%'")
    )
    await session.commit()


async def create_project(session: AsyncSession, name: str = "单测-临时项目") -> Project:
    project = Project(name=name, coordinate_system="Gauss-Kruger")
    session.add(project)
    await session.commit()
    return project


async def create_job(
    session: AsyncSession,
    project_id: str,
    *,
    status: str = "pending",
    attempts: int = 0,
    heartbeat: datetime | None = None,
    error: str | None = None,
) -> ModelingJob:
    job = ModelingJob(
        project_id=project_id,
        status=status,
        stage="排队中",
        message="等待建模",
        attempts=attempts,
        params_json={},
        input_strata_path="inputs/strata.xlsx",
        input_location_path="inputs/location.xlsx",
        last_heartbeat_at=heartbeat,
        error_message=error,
    )
    session.add(job)
    await session.commit()
    return job


async def fetch_job(job_id: str) -> ModelingJob | None:
    """从**新会话**重新读任务行。

    为什么不用 ``session.refresh()``:MySQL 默认 REPEATABLE READ,调用方那个会话
    在上一次 SELECT/commit 之后已经开了事务、拿住了快照,refresh 仍然看到旧值。
    要观察其它会话(比如 worker)写入的结果,必须开新事务。
    """
    async with AsyncSessionFactory() as session:
        return await session.get(ModelingJob, job_id)


async def drop_project(project_id: str) -> None:
    """清掉临时项目。先解掉 model_assets ↔ model_versions 的循环引用再删。"""
    async with AsyncSessionFactory() as session:
        await session.execute(
            text("UPDATE model_assets SET current_version_id = NULL WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await session.execute(delete(ModelAsset).where(ModelAsset.project_id == project_id))
        await session.execute(text("DELETE FROM projects WHERE id = :pid"), {"pid": project_id})
        await session.commit()


def utc_now() -> datetime:
    return datetime.now(UTC)
