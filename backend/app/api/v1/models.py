from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile, status

from app.api.dependencies import DbSession
from app.core.config import settings
from app.schemas.asset import (
    ModelAssetCreate,
    ModelAssetRead,
    ModelAssetUpdate,
    ModelUploadResult,
)
from app.schemas.common import DataResponse
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
