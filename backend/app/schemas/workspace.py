from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

class TimestampedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class WorkingFaceRead(TimestampedRead):

    project_id: str
    code: str
    name: str
    status: str
    description: str | None
    model_asset_id: str | None
    length: float | None
    width: float | None
    coal_seam: str | None
    metadata_json: dict[str, Any]


class ImportRunRead(TimestampedRead):
    project_id: str
    source: str
    status: str
    summary_json: dict[str, Any]
    error_message: str | None


class ImportSummary(BaseModel):
    project_id: str
    boreholes: int
    borehole_segments: int
    model_assets: int
    working_faces: int
    zero_thickness_segments: int
