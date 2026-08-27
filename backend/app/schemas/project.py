from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    coordinate_system: str = Field(default="local", max_length=64)
    origin_x: float = 0
    origin_y: float = 0
    origin_z: float = 0
    vertical_scale: float = Field(default=1, gt=0)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    coordinate_system: str | None = Field(default=None, max_length=64)
    origin_x: float | None = None
    origin_y: float | None = None
    origin_z: float | None = None
    vertical_scale: float | None = Field(default=None, gt=0)


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
