from fastapi import APIRouter, Response, status

from app.api.dependencies import DbSession
from app.schemas.common import DataResponse
from app.schemas.scene import SceneConfigCreate, SceneConfigRead, SceneConfigUpdate
from app.services.workspace_service import SceneService


router = APIRouter()


@router.get("/projects/{project_id}/scenes", response_model=DataResponse[list[SceneConfigRead]])
async def list_scenes(project_id: str, session: DbSession):
    return DataResponse(data=await SceneService(session).list(project_id))


@router.post(
    "/projects/{project_id}/scenes",
    response_model=DataResponse[SceneConfigRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_scene(project_id: str, payload: SceneConfigCreate, session: DbSession):
    return DataResponse(data=await SceneService(session).create(project_id, payload))


@router.get("/scenes/{scene_id}", response_model=DataResponse[SceneConfigRead])
async def get_scene(scene_id: str, session: DbSession):
    return DataResponse(data=await SceneService(session).get_or_404(scene_id))


@router.put("/scenes/{scene_id}", response_model=DataResponse[SceneConfigRead])
async def update_scene(scene_id: str, payload: SceneConfigUpdate, session: DbSession):
    return DataResponse(data=await SceneService(session).update(scene_id, payload))


@router.delete("/scenes/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene(scene_id: str, session: DbSession):
    await SceneService(session).delete(scene_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
