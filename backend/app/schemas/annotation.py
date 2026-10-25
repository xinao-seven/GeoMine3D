from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnnotationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str | None = None
    position_x: float
    position_y: float
    position_z: float
    color: str = Field(default="#e7b75f", max_length=16)


class AnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    position_x: float
    position_y: float
    position_z: float
    title: str
    content: str | None
    color: str
    created_at: datetime
