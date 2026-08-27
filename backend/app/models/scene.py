from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class SceneConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scene_configs"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    camera_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    layers_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    clipping_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    explode_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    render_settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="scenes")


class Annotation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "annotations"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    scene_id: Mapped[str | None] = mapped_column(
        ForeignKey("scene_configs.id", ondelete="SET NULL"), index=True
    )
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(36))
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    position_z: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(16), default="#e7b75f", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="annotations")
