from fastapi import APIRouter, Response, status

from app.api.dependencies import DbSession
from app.schemas.borehole import (
    BoreholeCreate,
    BoreholeRead,
    BoreholeSegmentInput,
    BoreholeUpdate,
)
from app.schemas.common import DataResponse
from app.services.workspace_service import BoreholeService


router = APIRouter()


@router.get("/projects/{project_id}/boreholes", response_model=DataResponse[list[BoreholeRead]])
async def list_boreholes(project_id: str, session: DbSession):
    return DataResponse(data=await BoreholeService(session).list(project_id))


@router.post(
    "/projects/{project_id}/boreholes",
    response_model=DataResponse[BoreholeRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_borehole(project_id: str, payload: BoreholeCreate, session: DbSession):
    return DataResponse(data=await BoreholeService(session).create(project_id, payload))


@router.get("/boreholes/{borehole_id}", response_model=DataResponse[BoreholeRead])
async def get_borehole(borehole_id: str, session: DbSession):
    return DataResponse(data=await BoreholeService(session).get_or_404(borehole_id))


@router.patch("/boreholes/{borehole_id}", response_model=DataResponse[BoreholeRead])
async def update_borehole(borehole_id: str, payload: BoreholeUpdate, session: DbSession):
    return DataResponse(data=await BoreholeService(session).update(borehole_id, payload))


@router.put("/boreholes/{borehole_id}/segments", response_model=DataResponse[BoreholeRead])
async def replace_borehole_segments(
    borehole_id: str, payload: list[BoreholeSegmentInput], session: DbSession
):
    return DataResponse(data=await BoreholeService(session).replace_segments(borehole_id, payload))


@router.delete("/boreholes/{borehole_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_borehole(borehole_id: str, session: DbSession):
    await BoreholeService(session).delete(borehole_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
