from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModelingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    stage: str | None
    message: str | None
    attempts: int = 0
    # 实时百分比来自 Redis 快照(引擎阶段埋点),库里的建模任务不存进度
    percent: float = 0.0
    params_json: dict[str, Any]
    output_dir: str | None
    result_json: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ModelingJobCreateForm(BaseModel):
    """multipart 表单字段的类型化描述(校验在路由层完成)。"""

    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
