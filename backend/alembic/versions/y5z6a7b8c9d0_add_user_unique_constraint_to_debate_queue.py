"""add user unique constraint to debate queue

유저당 1개 대기열 제한 — debate_match_queue.user_id에 UNIQUE 제약 추가

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-02-28
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "y5z6a7b8c9d0"
down_revision = "x4y5z6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_debate_queue_user",
        "debate_match_queue",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_debate_queue_user",
        "debate_match_queue",
        type_="unique",
    )
