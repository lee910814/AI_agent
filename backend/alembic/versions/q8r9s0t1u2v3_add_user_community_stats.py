"""user_community_stats 테이블 추가 — 사용자 커뮤니티 참여등급 집계.

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-03-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "q8r9s0t1u2v3"
down_revision: str = "p7q8r9s0t1u2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_community_stats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tier", sa.String(20), nullable=False, server_default="Bronze"),
        sa.Column("likes_given", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("follows_given", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_community_stats_user_id"),
    )
    op.create_index("idx_user_community_stats_user_id", "user_community_stats", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_user_community_stats_user_id", table_name="user_community_stats")
    op.drop_table("user_community_stats")
