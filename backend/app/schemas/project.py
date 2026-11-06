"""项目的请求/响应模型。

``origin_*`` 与 ``vertical_scale`` 定义"真实坐标 → 场景坐标"的还原参数，
由锦界 catalog 或建模引擎写回，前端不手工填。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    """项目基础字段（创建与读取共用）。"""

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
