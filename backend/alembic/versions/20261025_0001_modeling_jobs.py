"""Add modeling jobs for async borehole-to-model generation.

Revision ID: 20261025_0001
Revises: 20260828_0003
Create Date: 2026-10-25
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20261025_0001"
down_revision: str | None = "20260828_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "modeling_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("stage", sa.String(64)),
        sa.Column("message", sa.Text()),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("input_strata_path", sa.String(500), nullable=False),
        sa.Column("input_location_path", sa.String(500), nullable=False),
        sa.Column("output_dir", sa.String(500)),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        *timestamp_columns(),
    )
    op.create_index("ix_modeling_jobs_project_id", "modeling_jobs", ["project_id"])
    op.create_index("ix_modeling_jobs_status", "modeling_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("modeling_jobs")
