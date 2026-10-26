from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import DbSession
from app.core.config import settings
from app.core.exceptions import AppError
from app.models.asset import ModelVersion
from app.schemas.asset import (
    ModelAssetCreate,
    ModelAssetRead,
    ModelAssetUpdate,
    ModelUploadResult,
)
from app.schemas.common import DataResponse
from app.services.model_paths import resolve_variant_path
from app.services.workspace_service import ModelService


router = APIRouter()


@router.get("/projects/{project_id}/models", response_model=DataResponse[list[ModelAssetRead]])
async def list_models(project_id: str, session: DbSession):
    return DataResponse(data=await ModelService(session).list(project_id))


@router.post(
    "/projects/{project_id}/models",
    response_model=DataResponse[ModelAssetRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_model(project_id: str, payload: ModelAssetCreate, session: DbSession):
    return DataResponse(data=await ModelService(session).create(project_id, payload))


@router.get("/models/{model_id}", response_model=DataResponse[ModelAssetRead])
async def get_model(model_id: str, session: DbSession):
    return DataResponse(data=await ModelService(session).get_or_404(model_id))


@router.get("/models/{model_id}/file", response_class=FileResponse)
async def get_model_file(
    model_id: str,
    session: DbSession,
    variant: Literal["render", "shell"] = "render",
):
    """下载模型文件。

    ``variant`` 选择几何轨(建模引擎对同一个分段体元集合同时导出两套产物):

    - ``render``(默认):``L*.glb`` / ``model_combined.glb``,含内部棱柱壁,
      剖切后内部为柱状实体、无需补面;非水密,渲染端需 ``DoubleSide``。
    - ``shell``:``shells/*_shell.glb``,闭合水密壳,供剖面求交/体积/等值线等
      数值分析。旧交付包没有分析轨时返回 404(不会隐式回退到渲染网格,
      否则分析代码会与内部壁求交得到错误结果)。
    """
    asset = await ModelService(session).get_or_404(model_id)
    if not asset.current_version_id:
        raise AppError("MODEL_FILE_NOT_FOUND", "模型尚未上传文件", status_code=404)
    version = await session.get(ModelVersion, asset.current_version_id)
    if version is None:
        raise AppError("MODEL_FILE_NOT_FOUND", "模型版本不存在", status_code=404)
    roots = {
        "upload": settings.upload_path,
        "server_static": settings.source_model_path,
    }
    root = roots.get(version.storage_scope)
    if root is None:
        raise AppError("MODEL_STORAGE_INVALID", "模型存储位置无效", status_code=500)
    metadata = asset.metadata_json or {}
    relative_path = resolve_variant_path(metadata, variant, version.file_path)
    if relative_path is None:
        if variant == "shell":
            raise AppError(
                "MODEL_SHELL_NOT_FOUND",
                "该模型没有分析轨(闭合壳)产物,请用 variant=render 或重新生成交付包",
                status_code=404,
            )
        raise AppError("MODEL_FILE_NOT_FOUND", "模型文件不存在", status_code=404)
    root = root.resolve()
    path = (root / relative_path).resolve()
    if root not in path.parents or not path.is_file():
        code = "MODEL_SHELL_NOT_FOUND" if variant == "shell" else "MODEL_FILE_NOT_FOUND"
        raise AppError(code, f"模型文件不存在: {relative_path}", status_code=404)
    media_type = "model/gltf+json" if path.suffix.lower() == ".gltf" else "model/gltf-binary"
    return FileResponse(
        path,
        filename=path.name,
        media_type=media_type,
        # 同一 URL 的交付包会随重新生成而变(旧包为闭合壳、新包含内部壁),
        # 浏览器启发式缓存会导致“时而空心”的不可复现现象,这里强制回源校验。
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@router.patch("/models/{model_id}", response_model=DataResponse[ModelAssetRead])
async def update_model(model_id: str, payload: ModelAssetUpdate, session: DbSession):
    return DataResponse(data=await ModelService(session).update(model_id, payload))


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(model_id: str, session: DbSession):
    await ModelService(session).delete(model_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/models/{model_id}/versions",
    response_model=DataResponse[ModelUploadResult],
    status_code=status.HTTP_201_CREATED,
)
async def upload_model_version(
    model_id: str,
    session: DbSession,
    file: Annotated[UploadFile, File(description="GLB or glTF model")],
    draco_compressed: Annotated[bool, Form()] = False,
):
    service = ModelService(session)
    version = await service.add_version(model_id, file, draco_compressed)
    asset = await service.get_or_404(model_id)
    return DataResponse(
        data=ModelUploadResult(
            asset=ModelAssetRead.model_validate(asset),
            version=version,
            file_url=f"{settings.model_public_prefix}/{version.file_path}",
        )
    )
