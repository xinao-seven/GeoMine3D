"""ORM 公共 mixin：UUID 字符串主键与创建/更新时间戳。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


def uuid_str() -> str:
    """32 位连字符 UUID（String(36) 主键的默认值）。"""
    return str(uuid.uuid4())


class UUIDPrimaryKeyMixin:
    """字符串 UUID 主键（避免自增 ID 泄漏规模、便于跨环境同步）。"""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)


class TimestampMixin:
    """created_at / updated_at（由数据库维护，读侧不需赋值）。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
