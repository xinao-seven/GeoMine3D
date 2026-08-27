"""Create GeoMine3D core schema.

Revision ID: 20260827_0001
Revises:
Create Date: 2026-08-27
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260827_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("coordinate_system", sa.String(64), nullable=False),
        sa.Column("origin_x", sa.Float(), nullable=False),
        sa.Column("origin_y", sa.Float(), nullable=False),
        sa.Column("origin_z", sa.Float(), nullable=False),
        sa.Column("vertical_scale", sa.Float(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_projects_name", "projects", ["name"])

    op.create_table(
        "model_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("model_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("current_version_id", sa.String(36)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_model_assets_project_id", "model_assets", ["project_id"])
    op.create_index("ix_model_assets_model_type", "model_assets", ["model_type"])

    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "model_id", sa.String(36), sa.ForeignKey("model_assets.id", ondelete="CASCADE")
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("draco_compressed", sa.Boolean(), nullable=False),
        sa.Column("vertex_count", sa.BigInteger()),
        sa.Column("triangle_count", sa.BigInteger()),
        sa.Column("bbox_json", sa.JSON()),
        *timestamp_columns(),
        sa.UniqueConstraint("model_id", "version", name="uq_model_version"),
    )
    op.create_index("ix_model_versions_model_id", "model_versions", ["model_id"])
    op.create_index("ix_model_versions_content_hash", "model_versions", ["content_hash"])

    op.create_table(
        "geological_layers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "model_id", sa.String(36), sa.ForeignKey("model_assets.id", ondelete="CASCADE")
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("code", sa.String(64)),
        sa.Column("layer_index", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(16), nullable=False),
        sa.Column("opacity", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_geological_layers_model_id", "geological_layers", ["model_id"])

    op.create_table(
        "boreholes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("z", sa.Float(), nullable=False),
        sa.Column("total_depth", sa.Float(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamp_columns(),
        sa.UniqueConstraint("project_id", "code", name="uq_project_borehole_code"),
    )
    op.create_index("ix_boreholes_project_id", "boreholes", ["project_id"])
    op.create_index("ix_boreholes_code", "boreholes", ["code"])

    op.create_table(
        "borehole_segments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "borehole_id", sa.String(36), sa.ForeignKey("boreholes.id", ondelete="CASCADE")
        ),
        sa.Column("layer_name", sa.String(120), nullable=False),
        sa.Column("lithology", sa.String(120)),
        sa.Column("top_depth", sa.Float(), nullable=False),
        sa.Column("bottom_depth", sa.Float(), nullable=False),
        sa.Column("thickness", sa.Float(), nullable=False),
        sa.Column("color", sa.String(16), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_borehole_segments_borehole_id", "borehole_segments", ["borehole_id"])

    op.create_table(
        "scene_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("camera_json", sa.JSON(), nullable=False),
        sa.Column("layers_json", sa.JSON(), nullable=False),
        sa.Column("clipping_json", sa.JSON(), nullable=False),
        sa.Column("explode_json", sa.JSON(), nullable=False),
        sa.Column("render_settings_json", sa.JSON(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_scene_configs_project_id", "scene_configs", ["project_id"])

    op.create_table(
        "annotations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column(
            "scene_id", sa.String(36), sa.ForeignKey("scene_configs.id", ondelete="SET NULL")
        ),
        sa.Column("target_type", sa.String(32)),
        sa.Column("target_id", sa.String(36)),
        sa.Column("position_x", sa.Float(), nullable=False),
        sa.Column("position_y", sa.Float(), nullable=False),
        sa.Column("position_z", sa.Float(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("color", sa.String(16), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_annotations_project_id", "annotations", ["project_id"])
    op.create_index("ix_annotations_scene_id", "annotations", ["scene_id"])


def downgrade() -> None:
    op.drop_table("annotations")
    op.drop_table("scene_configs")
    op.drop_table("borehole_segments")
    op.drop_table("boreholes")
    op.drop_table("geological_layers")
    op.drop_table("model_versions")
    op.drop_table("model_assets")
    op.drop_table("projects")
