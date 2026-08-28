"""Add model storage scopes, working faces and import audit records.

Revision ID: 20260828_0002
Revises: 20260827_0001
Create Date: 2026-08-28
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260828_0002"
down_revision: str | None = "20260827_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.add_column(
        "model_versions",
        sa.Column("storage_scope", sa.String(24), server_default="upload", nullable=False),
    )
    op.create_foreign_key(
        "fk_model_assets_current_version",
        "model_assets",
        "model_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )

    op.create_table(
        "working_faces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "model_asset_id",
            sa.String(36),
            sa.ForeignKey("model_assets.id", ondelete="SET NULL"),
        ),
        sa.Column("length", sa.Float()),
        sa.Column("width", sa.Float()),
        sa.Column("coal_seam", sa.String(64)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamp_columns(),
        sa.UniqueConstraint("project_id", "code", name="uq_project_working_face_code"),
    )
    op.create_index("ix_working_faces_project_id", "working_faces", ["project_id"])
    op.create_index("ix_working_faces_code", "working_faces", ["code"])
    op.create_index("ix_working_faces_model_asset_id", "working_faces", ["model_asset_id"])

    op.create_table(
        "import_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        *timestamp_columns(),
    )
    op.create_index("ix_import_runs_project_id", "import_runs", ["project_id"])


def downgrade() -> None:
    op.drop_table("import_runs")
    op.drop_table("working_faces")
    op.drop_constraint("fk_model_assets_current_version", "model_assets", type_="foreignkey")
    op.drop_column("model_versions", "storage_scope")
