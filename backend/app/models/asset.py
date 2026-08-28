from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ModelAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_assets"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), default="ready", nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "model_versions.id",
            name="fk_model_assets_current_version",
            ondelete="SET NULL",
            use_alter=True,
        )
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="models")
    versions: Mapped[list["ModelVersion"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
        foreign_keys="ModelVersion.model_id",
    )
    layers: Mapped[list["GeologicalLayer"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class ModelVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_id", "version", name="uq_model_version"),)

    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_assets.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_scope: Mapped[str] = mapped_column(String(24), default="upload", nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    draco_compressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vertex_count: Mapped[int | None] = mapped_column(BigInteger)
    triangle_count: Mapped[int | None] = mapped_column(BigInteger)
    bbox_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    model: Mapped["ModelAsset"] = relationship(
        back_populates="versions", foreign_keys=[model_id]
    )


class GeologicalLayer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "geological_layers"

    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_assets.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64))
    layer_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#7b8d78", nullable=False)
    opacity: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    model: Mapped["ModelAsset"] = relationship(back_populates="layers")
