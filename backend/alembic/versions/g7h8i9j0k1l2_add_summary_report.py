"""add summary_report to debate_matches

기능 11: 토론 요약 리포트 — debate_matches.summary_report JSONB 컬럼 추가.

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g7h8i9j0k1l2"
down_revision = "f6g7h8i9j0k1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "debate_matches",
        sa.Column("summary_report", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("debate_matches", "summary_report")
