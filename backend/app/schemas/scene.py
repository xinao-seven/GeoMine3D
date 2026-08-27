from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SceneConfigBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    camera_json: dict[str, Any] = Field(default_factory=dict)
    layers_json: list[dict[str, Any]] = Field(default_factory=list)
    clipping_json: dict[str, Any] = Field(default_factory=dict)
    explode_json: dict[str, Any] = Field(default_factory=dict)
    render_settings_json: dict[str, Any] = Field(default_factory=dict)


class SceneConfigCreate(SceneConfigBase):
    pass


class SceneConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    camera_json: dict[str, Any] | None = None
    layers_json: list[dict[str, Any]] | None = None
    clipping_json: dict[str, Any] | None = None
    explode_json: dict[str, Any] | None = None
    render_settings_json: dict[str, Any] | None = None


class SceneConfigRead(SceneConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime
