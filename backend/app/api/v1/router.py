from fastapi import APIRouter

from app.api.v1 import boreholes, models, projects, scenes, workspace


api_router = APIRouter()
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(boreholes.router, tags=["boreholes"])
api_router.include_router(scenes.router, tags=["scenes"])
api_router.include_router(workspace.router, tags=["workspace"])
