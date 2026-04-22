"""add expires_at to debate_match_queue

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa

revision = 'l2m3n4o5p6q7'
down_revision = 'k1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # nullable=True로 먼저 추가하여 기존 행에 기본값 설정 가능하게 함
    op.add_column(
        "debate_match_queue",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    # 기존 행 backfill: joined_at + 120초
    op.execute(
        "UPDATE debate_match_queue SET expires_at = joined_at + INTERVAL '120 seconds'"
    )
    # NOT NULL 제약 추가
    op.alter_column("debate_match_queue", "expires_at", nullable=False)


def downgrade() -> None:
    op.drop_column("debate_match_queue", "expires_at")
