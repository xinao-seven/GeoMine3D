"""Single model root: normalize model_versions.storage_scope.

所有模型文件已统一到 ``settings.source_model_path``(默认 ``server/static/models``),
统一挂载 ``/static/models``;``storage_scope`` 只剩历史兼容意义,新写入一律
``server_static``。本迁移把列默认值与存量行对齐(文件搬迁由
``backend/scripts/migrate_models_single_root.py`` 完成,与本迁移无关)。

Revision ID: 20261030_0001
Revises: 20261025_0001
Create Date: 2026-10-30
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20261030_0001"
down_revision: str | None = "20261025_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "model_versions",
        "storage_scope",
        existing_type=sa.String(24),
        server_default="server_static",
        existing_nullable=False,
    )
    op.execute(
        "UPDATE model_versions SET storage_scope = 'server_static' "
        "WHERE storage_scope <> 'server_static'"
    )


def downgrade() -> None:
    op.alter_column(
        "model_versions",
        "storage_scope",
        existing_type=sa.String(24),
        server_default="upload",
        existing_nullable=False,
    )
