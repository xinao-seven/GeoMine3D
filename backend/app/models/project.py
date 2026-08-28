from typing import TYPE_CHECKING

from sqlalchemy import Double, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.asset import ModelAsset
    from app.models.borehole import Borehole
    from app.models.scene import Annotation, SceneConfig
    from app.models.workspace import ImportRun, WorkingFace


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    coordinate_system: Mapped[str] = mapped_column(String(64), default="local", nullable=False)
    origin_x: Mapped[float] = mapped_column(Double, default=0, nullable=False)
    origin_y: Mapped[float] = mapped_column(Double, default=0, nullable=False)
    origin_z: Mapped[float] = mapped_column(Double, default=0, nullable=False)
    vertical_scale: Mapped[float] = mapped_column(Float, default=1, nullable=False)

    models: Mapped[list["ModelAsset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    boreholes: Mapped[list["Borehole"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scenes: Mapped[list["SceneConfig"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    working_faces: Mapped[list["WorkingFace"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    import_runs: Mapped[list["ImportRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
