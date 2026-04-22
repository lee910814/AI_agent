"""debate_turn_logs에 LLM 검토 결과 컬럼 추가

Revision ID: s9n0o1p2q3r4
Revises: r8m9n0o1p2q3
Create Date: 2026-02-25

Changes:
- debate_turn_logs.review_result (JSONB, nullable): LLM 검토 결과
  {"logic_score": 7, "violations": [...], "feedback": "...", "blocked": false}
- debate_turn_logs.is_blocked (Boolean, NOT NULL, default false): 차단 여부
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "s9n0o1p2q3r4"
down_revision = "r8m9n0o1p2q3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "debate_turn_logs",
        sa.Column("review_result", JSONB, nullable=True),
    )
    op.add_column(
        "debate_turn_logs",
        sa.Column(
            "is_blocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("debate_turn_logs", "is_blocked")
    op.drop_column("debate_turn_logs", "review_result")
