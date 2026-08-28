from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class WorkingFace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "working_faces"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_project_working_face_code"),)

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="规划中", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    model_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_assets.id", ondelete="SET NULL"), index=True
    )
    length: Mapped[float | None] = mapped_column(Float)
    width: Mapped[float | None] = mapped_column(Float)
    coal_seam: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="working_faces")


class ImportRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_runs"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped["Project"] = relationship(back_populates="import_runs")
