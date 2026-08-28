"""Use double precision for projected coordinates.

Revision ID: 20260828_0003
Revises: 20260828_0002
Create Date: 2026-08-28
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260828_0003"
down_revision: str | None = "20260828_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("origin_x", "origin_y", "origin_z"):
        op.alter_column("projects", column, existing_type=sa.Float(), type_=sa.Double())
    for column in ("x", "y", "z"):
        op.alter_column("boreholes", column, existing_type=sa.Float(), type_=sa.Double())


def downgrade() -> None:
    for column in ("x", "y", "z"):
        op.alter_column("boreholes", column, existing_type=sa.Double(), type_=sa.Float())
    for column in ("origin_x", "origin_y", "origin_z"):
        op.alter_column("projects", column, existing_type=sa.Double(), type_=sa.Float())
