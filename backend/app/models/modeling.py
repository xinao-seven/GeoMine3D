from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ModelingJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """钻孔 Excel 异步建模任务。

    生命周期: pending → running → completed | failed。
    上传的分层/位置 Excel 与引擎日志都保存在 uploads/modeling-jobs/<id>/ 下,
    生成的交付包写入 uploads/projects/<project_id>/web_package/,二者均为
    相对 upload_path 的 POSIX 路径。
    """

    __tablename__ = "modeling_jobs"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, index=True)
    stage: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str | None] = mapped_column(Text)
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    input_strata_path: Mapped[str] = mapped_column(String(500), nullable=False)
    input_location_path: Mapped[str] = mapped_column(String(500), nullable=False)
    output_dir: Mapped[str | None] = mapped_column(String(500))
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped["Project"] = relationship(back_populates="modeling_jobs")
