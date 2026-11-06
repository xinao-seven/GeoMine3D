"""模型资产端点：资产 CRUD、双轨文件下载（render/shell，带 ETag 条件请求）与版本上传。

下载链路里的缓存/条件请求逻辑（``_file_etag`` / ``_etag_matches``）是 HTTP 关注点，
留在路由层；数据访问与 404 语义在 ``workspace_service.ModelService``。
"""

import hashlib
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import DbSession
from app.core.exceptions import AppError
from app.schemas.asset import (
    ModelAssetCreate,
    ModelAssetRead,
    ModelAssetUpdate,
    ModelUploadResult,
)
from app.schemas.common import DataResponse
from app.services.model_paths import PUBLIC_PREFIX, resolve_model_file, resolve_variant_path
from app.services.workspace_service import ModelService

router = APIRouter()


def _file_etag(path: Path, content_hash: str | None) -> str:
    """强校验器:优先用库里记录的内容哈希(sha256),没有则回退到 mtime+size。

    为什么不用 Starlette 内置的那一个:它在 ``__call__`` 里才生成,构造响应时拿不到;
    而条件请求必须在读文件之前判断。顺手把 ETag 升级成**内容哈希**,与“内容寻址”
    的整体思路一致(重建交付包后 mtime 可能碰巧相同,内容哈希不会)。
    """
    if content_hash:
        return f'"{content_hash[:32]}"'
    stat = path.stat()
    base = f"{stat.st_mtime}-{stat.st_size}"
    return f'"{hashlib.md5(base.encode(), usedforsecurity=False).hexdigest()}"'


def _etag_matches(if_none_match: str | None, etag: str) -> bool:
    """实现 RFC 9110 的条件请求:``*`` / 逐个 etag 比对(容忍弱校验前缀 W/)。"""
    if not if_none_match:
        return False
    if if_none_match.strip() == "*":
        return True
    target = etag.strip().lstrip("W/")
    for candidate in if_none_match.split(","):
        if candidate.strip().lstrip("W/") == target:
            return True
    return False


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
    request: Request,
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
    version = await ModelService(session).get_current_version_or_404(asset)
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
    path = resolve_model_file(relative_path)
    if path is None:
        code = "MODEL_SHELL_NOT_FOUND" if variant == "shell" else "MODEL_FILE_NOT_FOUND"
        raise AppError(code, f"模型文件不存在: {relative_path}", status_code=404)
    media_type = "model/gltf+json" if path.suffix.lower() == ".gltf" else "model/gltf-binary"
    # 同一 URL 的交付包会随重新生成而变(旧包为闭合壳、新包含内部壁),因此不下发
    # 长缓存;但配合 ETag 协商,回源时只需要一个 304(几十字节)而不是重下 20MB+。
    etag = _file_etag(path, version.content_hash)
    cache_control = "no-cache, must-revalidate"
    # Starlette 0.47 的 FileResponse 支持 Range(206) 但**不做**条件请求,这里补 304。
    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"ETag": etag, "Cache-Control": cache_control},
        )
    return FileResponse(
        path,
        filename=path.name,
        media_type=media_type,
        headers={"Cache-Control": cache_control, "ETag": etag},
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
            file_url=f"{PUBLIC_PREFIX}/{version.file_path}",
        )
    )
