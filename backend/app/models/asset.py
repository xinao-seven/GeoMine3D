"""模型资产 ORM：资产(model_assets) / 版本(model_versions) / 地质层(geological_layers)。

路径契约：``model_versions.file_path`` 与 ``metadata_json`` 里的文件路径都是相对
模型根目录（``settings.source_model_path``）的 posix 相对路径，解析集中在
``app/services/model_paths.py``。
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ModelAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """模型资产（一个可加载的模型对象，如某地层/合并场景/上传的 GLB）。

    建模产物的资产 identity 是 ``(project_id, metadata.catalog_code)``，
    重试/重建按它幂等覆盖，而不是按文件路径（路径随内容指纹变化）。
    """

    __tablename__ = "model_assets"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # stratum=地层模型 / combined=合并场景 / 其他值用于上传的自定义模型
    model_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), default="ready", nullable=False)
    # 指向"当前生效"的版本；use_alter 避开 assets↔versions 的循环外键
    current_version_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "model_versions.id",
            name="fk_model_assets_current_version",
            ondelete="SET NULL",
            use_alter=True,
        )
    )
    # 双轨几何(source_file/shell_file)、LOD、包指纹(package_hash)等，契约见 model_paths
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
    """资产的一个文件版本（不可变：写好后只被指向，不被修改）。"""

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_id", "version", name="uq_model_version"),)

    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_assets.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    # 历史字段:模型文件已统一到单一模型根目录,新写入一律 server_static。
    storage_scope: Mapped[str] = mapped_column(
        String(24), default="server_static", nullable=False
    )
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # sha256 内容指纹：下载接口的强 ETag、静态 URL 的 ?v= 版本号、分析缓存失效依据
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    draco_compressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vertex_count: Mapped[int | None] = mapped_column(BigInteger)
    triangle_count: Mapped[int | None] = mapped_column(BigInteger)
    bbox_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    model: Mapped["ModelAsset"] = relationship(
        back_populates="versions", foreign_keys=[model_id]
    )


class GeologicalLayer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """资产的地质层元数据（层名/序号/颜色），图例与图表配色共用。"""
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
