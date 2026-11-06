"""工作台领域服务：模型资产 / 钻孔 / 场景配置 / 工作面与导入历史。

这些对象共同构成 ``/workspace/:projectId`` 工作台的资源树与状态，CRUD 语义相近
（service 持有请求级 ``AsyncSession``，负责校验项目存在 + 404 语义），因此集中放在
一个模块。跨域的通用工具（模型文件路径解析）见 ``model_paths.py``。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.asset import ModelAsset, ModelVersion
from app.models.borehole import Borehole, BoreholeSegment
from app.models.project import Project
from app.models.scene import SceneConfig
from app.models.workspace import ImportRun, WorkingFace
from app.schemas.asset import ModelAssetCreate, ModelAssetUpdate
from app.schemas.borehole import BoreholeCreate, BoreholeSegmentInput, BoreholeUpdate
from app.schemas.scene import SceneConfigCreate, SceneConfigUpdate
from app.services.model_paths import relative_to_root, user_upload_dir


async def ensure_project(session: AsyncSession, project_id: str) -> None:
    """项目存在性守卫：不存在时抛 404。所有项目级端点的第一步。"""
    if await session.get(Project, project_id) is None:
        raise AppError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)


async def list_working_faces(session: AsyncSession, project_id: str) -> list[WorkingFace]:
    """项目的工作面列表（按编号排序），资源树“工作面”分组使用。"""
    await ensure_project(session, project_id)
    rows = await session.scalars(
        select(WorkingFace)
        .where(WorkingFace.project_id == project_id)
        .order_by(WorkingFace.code)
    )
    return list(rows)


async def list_import_runs(session: AsyncSession, project_id: str) -> list[ImportRun]:
    """项目的导入历史（按时间倒序），供前端展示最近一次导入的来源与摘要。"""
    await ensure_project(session, project_id)
    rows = await session.scalars(
        select(ImportRun)
        .where(ImportRun.project_id == project_id)
        .order_by(ImportRun.created_at.desc())
    )
    return list(rows)


class ModelService:
    """模型资产（分层/合并/自定义上传 GLB）与其版本的 CRUD。

    资产行携带 ``metadata_json``（双轨几何、LOD、包指纹等，契约见
    ``model_paths.py``），版本行持有真实的相对路径与内容哈希。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, project_id: str) -> list[ModelAsset]:
        """项目资产列表（按更新时间倒序）。"""
        await ensure_project(self.session, project_id)
        result = await self.session.scalars(
            select(ModelAsset)
            .where(ModelAsset.project_id == project_id)
            .order_by(ModelAsset.updated_at.desc())
        )
        return list(result)

    async def create(self, project_id: str, payload: ModelAssetCreate) -> ModelAsset:
        """手工登记一个模型资产（初始无版本，文件走 ``add_version`` 上传）。"""
        await ensure_project(self.session, project_id)
        asset = ModelAsset(project_id=project_id, **payload.model_dump())
        self.session.add(asset)
        await self.session.commit()
        await self.session.refresh(asset)
        return asset

    async def get_or_404(self, asset_id: str) -> ModelAsset:
        """按 ID 取资产，不存在抛 404。"""
        asset = await self.session.get(ModelAsset, asset_id)
        if asset is None:
            raise AppError("MODEL_NOT_FOUND", "模型不存在", status_code=404)
        return asset

    async def get_current_version_or_404(self, asset: ModelAsset) -> ModelVersion:
        """取资产当前版本的行；从未上传过文件或版本行缺失都按 404 处理。

        下载接口在判断条件请求(ETag)之前就需要版本的 ``content_hash``，
        所以必须拿到行本体而不是只看 ``current_version_id``。
        """
        if not asset.current_version_id:
            raise AppError("MODEL_FILE_NOT_FOUND", "模型尚未上传文件", status_code=404)
        version = await self.session.get(ModelVersion, asset.current_version_id)
        if version is None:
            raise AppError("MODEL_FILE_NOT_FOUND", "模型版本不存在", status_code=404)
        return version

    async def update(self, asset_id: str, payload: ModelAssetUpdate) -> ModelAsset:
        asset = await self.get_or_404(asset_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(asset, field, value)
        await self.session.commit()
        await self.session.refresh(asset)
        return asset

    async def delete(self, asset_id: str) -> Path | None:
        asset = await self.get_or_404(asset_id)
        version = None
        if asset.current_version_id:
            version = await self.session.get(ModelVersion, asset.current_version_id)
        await self.session.delete(asset)
        await self.session.commit()
        return Path(version.file_path) if version else None

    async def add_version(self, asset_id: str, upload: UploadFile, draco: bool) -> ModelVersion:
        """流式接收一个模型文件，登记为新版本并把资产指向它。

        - 扩展名只接受 ``.glb/.gltf``；大小按 ``max_upload_size_mb`` 限额（413）;
        - 写盘的同时计算 sha256（``content_hash``），它是下载接口的强 ETag 与
          分析缓存的失效依据;
        - 落在 ``user_uploads/<asset_id>/v<N>`` 下（相对模型根目录），任何异常都会
          删掉半成品文件后再抛出。
        """
        asset = await self.get_or_404(asset_id)
        suffix = Path(upload.filename or "model.glb").suffix.lower()
        if suffix not in {".glb", ".gltf"}:
            raise AppError("INVALID_MODEL_FILE", "仅支持 GLB 或 glTF 模型", status_code=415)

        next_version = int(
            await self.session.scalar(
                select(func.coalesce(func.max(ModelVersion.version), 0) + 1).where(
                    ModelVersion.model_id == asset_id
                )
            )
            or 1
        )
        asset_dir = user_upload_dir(asset.id)
        asset_dir.mkdir(parents=True, exist_ok=True)
        target = asset_dir / f"v{next_version}{suffix}"
        sha256 = hashlib.sha256()
        total = 0
        max_bytes = settings.max_upload_size_mb * 1024 * 1024

        try:
            with target.open("wb") as file_handle:
                while chunk := await upload.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise AppError("MODEL_TOO_LARGE", "模型文件超过上传限制", status_code=413)
                    sha256.update(chunk)
                    file_handle.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        version = ModelVersion(
            model_id=asset.id,
            version=next_version,
            file_path=relative_to_root(target),
            storage_scope="server_static",
            file_size=total,
            content_hash=sha256.hexdigest(),
            draco_compressed=draco,
        )
        self.session.add(version)
        await self.session.flush()
        asset.current_version_id = version.id
        asset.status = "ready"
        await self.session.commit()
        await self.session.refresh(version)
        return version


class BoreholeService:
    """钻孔与分层的 CRUD（工作台资源树与手工补录入口）。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, project_id: str) -> list[Borehole]:
        """项目钻孔列表（预加载分层；无分层数据的孔不进入资源树）。"""
        await ensure_project(self.session, project_id)
        result = await self.session.scalars(
            select(Borehole)
            .options(selectinload(Borehole.segments))
            .where(Borehole.project_id == project_id)
            .order_by(Borehole.code)
        )
        # 只展示有分层数据的钻孔:坐标表里有、分层表里没有的孔不进入资源树与场景。
        # 手工创建(无该标记)的钻孔默认保留。
        return [item for item in result if (item.metadata_json or {}).get("has_strata", True)]

    async def get_or_404(self, borehole_id: str) -> Borehole:
        result = await self.session.scalars(
            select(Borehole)
            .options(selectinload(Borehole.segments))
            .where(Borehole.id == borehole_id)
        )
        borehole = result.first()
        if borehole is None:
            raise AppError("BOREHOLE_NOT_FOUND", "钻孔不存在", status_code=404)
        return borehole

    async def create(self, project_id: str, payload: BoreholeCreate) -> Borehole:
        await ensure_project(self.session, project_id)
        values = payload.model_dump(exclude={"segments"})
        borehole = Borehole(project_id=project_id, **values)
        borehole.segments = [BoreholeSegment(**segment.model_dump()) for segment in payload.segments]
        self.session.add(borehole)
        await self.session.commit()
        return await self.get_or_404(borehole.id)

    async def update(self, borehole_id: str, payload: BoreholeUpdate) -> Borehole:
        borehole = await self.get_or_404(borehole_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(borehole, field, value)
        await self.session.commit()
        return await self.get_or_404(borehole.id)

    async def replace_segments(
        self, borehole_id: str, segments: list[BoreholeSegmentInput]
    ) -> Borehole:
        """整表替换某孔的分层（同步重算总深；前端“编辑分层”保存时调用）。"""
        borehole = await self.get_or_404(borehole_id)
        borehole.segments.clear()
        borehole.segments.extend(BoreholeSegment(**item.model_dump()) for item in segments)
        borehole.total_depth = max((item.bottom_depth for item in segments), default=0)
        await self.session.commit()
        return await self.get_or_404(borehole.id)

    async def delete(self, borehole_id: str) -> None:
        borehole = await self.get_or_404(borehole_id)
        await self.session.delete(borehole)
        await self.session.commit()


class SceneService:
    """场景配置（视角/图层/剖切/炸开状态的序列化快照）的 CRUD。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, project_id: str) -> list[SceneConfig]:
        """项目场景列表（按更新时间倒序）。"""
        await ensure_project(self.session, project_id)
        result = await self.session.scalars(
            select(SceneConfig)
            .where(SceneConfig.project_id == project_id)
            .order_by(SceneConfig.updated_at.desc())
        )
        return list(result)

    async def get_or_404(self, scene_id: str) -> SceneConfig:
        scene = await self.session.get(SceneConfig, scene_id)
        if scene is None:
            raise AppError("SCENE_NOT_FOUND", "场景配置不存在", status_code=404)
        return scene

    async def create(self, project_id: str, payload: SceneConfigCreate) -> SceneConfig:
        await ensure_project(self.session, project_id)
        scene = SceneConfig(project_id=project_id, **payload.model_dump())
        self.session.add(scene)
        await self.session.commit()
        await self.session.refresh(scene)
        return scene

    async def update(self, scene_id: str, payload: SceneConfigUpdate) -> SceneConfig:
        scene = await self.get_or_404(scene_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(scene, field, value)
        await self.session.commit()
        await self.session.refresh(scene)
        return scene

    async def delete(self, scene_id: str) -> None:
        scene = await self.get_or_404(scene_id)
        await self.session.delete(scene)
        await self.session.commit()
