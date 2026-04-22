"""add credits_deducted and error_reason to debate_matches

몰수패/부전패 처리 시 차감된 크레딧 금액과 오류/몰수 사유 기록:
- debate_matches.credits_deducted: 차감된 크레딧 (Numeric(10,6), nullable)
- debate_matches.error_reason: 오류 또는 몰수패 사유 (String(500), nullable)

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "debate_matches",
        sa.Column("credits_deducted", sa.Numeric(10, 6), nullable=True),
    )
    op.add_column(
        "debate_matches",
        sa.Column("error_reason", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("debate_matches", "error_reason")
    op.drop_column("debate_matches", "credits_deducted")
