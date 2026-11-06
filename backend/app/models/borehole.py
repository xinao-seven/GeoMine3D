"""钻孔 ORM：孔口(boreholes) 与分层段(borehole_segments)。

坐标语义：x/y 是高斯-克吕格投影坐标（前端再减项目原点转 Three.js 坐标），
z 是标高；深度(top/bottom/thickness)一律是孔口向下的米制深度。
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Double, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Borehole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """一个钻孔：孔口位置 + 总深 + 状态；分层数据在 ``segments`` 里。"""
    __tablename__ = "boreholes"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_project_borehole_code"),)

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    x: Mapped[float] = mapped_column(Double, nullable=False)
    y: Mapped[float] = mapped_column(Double, nullable=False)
    z: Mapped[float] = mapped_column(Double, nullable=False)
    total_depth: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="boreholes")
    segments: Mapped[list["BoreholeSegment"]] = relationship(
        back_populates="borehole",
        cascade="all, delete-orphan",
        order_by="BoreholeSegment.sequence",
    )


class BoreholeSegment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """钻孔的一个分层段（层名、顶/底深、厚度与展示颜色）。"""
    __tablename__ = "borehole_segments"

    borehole_id: Mapped[str] = mapped_column(
        ForeignKey("boreholes.id", ondelete="CASCADE"), index=True
    )
    layer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    lithology: Mapped[str | None] = mapped_column(String(120))
    top_depth: Mapped[float] = mapped_column(Float, nullable=False)
    bottom_depth: Mapped[float] = mapped_column(Float, nullable=False)
    thickness: Mapped[float] = mapped_column(Float, nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#8d7358", nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    borehole: Mapped["Borehole"] = relationship(back_populates="segments")
