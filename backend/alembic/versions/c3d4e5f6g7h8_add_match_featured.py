"""add is_featured and featured_at to debate_matches

기능 7: 주간 하이라이트 — is_featured, featured_at 컬럼 추가.

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6g7h8"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "debate_matches",
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "debate_matches",
        sa.Column("featured_at", sa.DateTime(timezone=True), nullable=True),
    )
    # partial 인덱스: featured 매치만 인덱싱해 스캔 비용 최소화
    op.execute(
        "CREATE INDEX idx_matches_featured ON debate_matches(is_featured, featured_at DESC) WHERE is_featured = true"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_matches_featured")
    op.drop_column("debate_matches", "featured_at")
    op.drop_column("debate_matches", "is_featured")
