from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BoreholeSegmentInput(BaseModel):
    layer_name: str = Field(min_length=1, max_length=120)
    lithology: str | None = Field(default=None, max_length=120)
    top_depth: float
    bottom_depth: float
    thickness: float | None = None
    color: str = Field(default="#8d7358", pattern=r"^#[0-9a-fA-F]{6}$")
    sequence: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_depths(self):
        if self.bottom_depth < self.top_depth:
            raise ValueError("bottom_depth 不能小于 top_depth")
        calculated = self.bottom_depth - self.top_depth
        if self.thickness is None:
            self.thickness = calculated
        elif abs(self.thickness - calculated) > 1e-6:
            raise ValueError("thickness 必须等于 bottom_depth - top_depth")
        return self


class BoreholeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    x: float
    y: float
    z: float
    total_depth: float = Field(default=0, ge=0)
    status: str = Field(default="active", max_length=24)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    segments: list[BoreholeSegmentInput] = Field(default_factory=list)


class BoreholeUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    x: float | None = None
    y: float | None = None
    z: float | None = None
    total_depth: float | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, max_length=24)
    metadata_json: dict[str, Any] | None = None


class BoreholeSegmentRead(BoreholeSegmentInput):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thickness: float


class BoreholeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    code: str
    name: str
    x: float
    y: float
    z: float
    total_depth: float
    status: str
    metadata_json: dict[str, Any]
    segments: list[BoreholeSegmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
