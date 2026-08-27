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
from app.schemas.asset import ModelAssetCreate, ModelAssetUpdate
from app.schemas.borehole import BoreholeCreate, BoreholeSegmentInput, BoreholeUpdate
from app.schemas.scene import SceneConfigCreate, SceneConfigUpdate


async def ensure_project(session: AsyncSession, project_id: str) -> None:
    if await session.get(Project, project_id) is None:
        raise AppError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)


class ModelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, project_id: str) -> list[ModelAsset]:
        await ensure_project(self.session, project_id)
        result = await self.session.scalars(
            select(ModelAsset)
            .where(ModelAsset.project_id == project_id)
            .order_by(ModelAsset.updated_at.desc())
        )
        return list(result)

    async def create(self, project_id: str, payload: ModelAssetCreate) -> ModelAsset:
        await ensure_project(self.session, project_id)
        asset = ModelAsset(project_id=project_id, **payload.model_dump())
        self.session.add(asset)
        await self.session.commit()
        await self.session.refresh(asset)
        return asset

    async def get_or_404(self, asset_id: str) -> ModelAsset:
        asset = await self.session.get(ModelAsset, asset_id)
        if asset is None:
            raise AppError("MODEL_NOT_FOUND", "模型不存在", status_code=404)
        return asset

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
        asset_dir = settings.upload_path / "models" / asset_id
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
            file_path=str(target.relative_to(settings.upload_path)).replace("\\", "/"),
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
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, project_id: str) -> list[Borehole]:
        await ensure_project(self.session, project_id)
        result = await self.session.scalars(
            select(Borehole)
            .options(selectinload(Borehole.segments))
            .where(Borehole.project_id == project_id)
            .order_by(Borehole.code)
        )
        return list(result)

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
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, project_id: str) -> list[SceneConfig]:
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
