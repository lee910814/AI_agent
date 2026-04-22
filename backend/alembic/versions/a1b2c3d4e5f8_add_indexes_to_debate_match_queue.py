"""add indexes to debate_match_queue

debate_match_queue.user_id, agent_id 단독 조회 시 풀스캔 방지

Revision ID: a1b2c3d4e5f8
Revises: z6a7b8c9d0e1
Create Date: 2026-02-28
"""

from alembic import op

revision = "a1b2c3d4e5f8"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_debate_queue_user_id", "debate_match_queue", ["user_id"])
    op.create_index("idx_debate_queue_agent_id", "debate_match_queue", ["agent_id"])


def downgrade() -> None:
    op.drop_index("idx_debate_queue_agent_id", table_name="debate_match_queue")
    op.drop_index("idx_debate_queue_user_id", table_name="debate_match_queue")
