"""建模任务重试与存活字段。

Redis Stream 队列需要三个事实来支撑“崩溃自愈”:

- ``attempts``:同一任务已尝试执行几次(每次开始执行 +1),超过上限进死信;
- ``next_retry_at``:指数退避的下次可见时间(写入 Redis ZSet 做延迟重投);
- ``last_heartbeat_at``:worker 活着就定期刷新,过期即视为僵死任务。

Revision ID: 20261105_0001
Revises: 20261030_0001
Create Date: 2026-11-05
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20261105_0001"
down_revision: str | None = "20261030_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "modeling_jobs",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "modeling_jobs",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "modeling_jobs",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("modeling_jobs", "last_heartbeat_at")
    op.drop_column("modeling_jobs", "next_retry_at")
    op.drop_column("modeling_jobs", "attempts")
