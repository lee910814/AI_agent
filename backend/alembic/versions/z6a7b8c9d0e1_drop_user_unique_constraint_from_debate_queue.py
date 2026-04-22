"""drop user unique constraint from debate queue

uq_debate_queue_user 제거 — admin 소프트웨어 체크와 DB 제약 충돌 해결.
유저당 1개 큐 제한은 debate_matching_service 소프트웨어 레이어에서만 관리한다.

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-02-28
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "z6a7b8c9d0e1"
down_revision = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_debate_queue_user",
        "debate_match_queue",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_debate_queue_user",
        "debate_match_queue",
        ["user_id"],
    )
