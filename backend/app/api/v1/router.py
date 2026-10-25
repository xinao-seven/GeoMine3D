from fastapi import APIRouter

from app.api.v1 import analysis, annotations, boreholes, boundaries, modeling, models, projects, remote, scenes, workspace


api_router = APIRouter()
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(boreholes.router, tags=["boreholes"])
api_router.include_router(scenes.router, tags=["scenes"])
api_router.include_router(workspace.router, tags=["workspace"])
api_router.include_router(remote.router, tags=["remote"])
api_router.include_router(modeling.router, tags=["modeling"])
api_router.include_router(analysis.router, tags=["analysis"])
api_router.include_router(boundaries.router, tags=["boundaries"])
api_router.include_router(annotations.router, tags=["annotations"])
