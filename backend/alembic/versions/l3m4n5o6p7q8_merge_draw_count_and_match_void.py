"""merge draw_count branch and match_void branch

두 독립 브랜치를 단일 헤드로 통합:
- k2l3m4n5o6p7: draw_count + expired status (promotion_series)
- o5p6q7r8s9t0: credits_deducted + error_reason (debate_matches)

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7, o5p6q7r8s9t0
Create Date: 2026-03-16
"""

from alembic import op

revision = "l3m4n5o6p7q8"
down_revision = ("k2l3m4n5o6p7", "o5p6q7r8s9t0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
