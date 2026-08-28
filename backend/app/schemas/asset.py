from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ModelType = Literal["stratum", "working_face", "other"]


class ModelAssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    model_type: ModelType
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ModelAssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    status: str | None = Field(default=None, max_length=24)
    metadata_json: dict[str, Any] | None = None


class ModelVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    file_path: str
    storage_scope: str
    file_size: int
    content_hash: str
    draco_compressed: bool
    vertex_count: int | None
    triangle_count: int | None
    bbox_json: dict[str, Any] | None
    created_at: datetime


class ModelAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    model_type: str
    status: str
    current_version_id: str | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ModelUploadResult(BaseModel):
    asset: ModelAssetRead
    version: ModelVersionRead
    file_url: str
