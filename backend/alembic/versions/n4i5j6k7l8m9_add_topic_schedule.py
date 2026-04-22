"""add_topic_schedule

Revision ID: n4i5j6k7l8m9
Revises: m3h4i5j6k7l8
Create Date: 2026-02-24 10:00:00.000000

debate_topics에 스케줄 컬럼 추가.
- scheduled_start_at: 토론 자동 시작 시각 (NULL = 즉시 open)
- scheduled_end_at:   토론 자동 종료 시각 (NULL = 수동 종료)
- is_admin_topic:     관리자 생성 토픽 여부
- status CHECK에 'scheduled' 추가
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "n4i5j6k7l8m9"
down_revision: Union[str, None] = "m3h4i5j6k7l8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("debate_topics", sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("debate_topics", sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("debate_topics", sa.Column("is_admin_topic", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("idx_debate_topics_schedule", "debate_topics", ["scheduled_end_at"], postgresql_where=sa.text("scheduled_end_at IS NOT NULL"))

    # status CHECK에 'scheduled' 추가
    op.execute("ALTER TABLE debate_topics DROP CONSTRAINT IF EXISTS ck_debate_topics_status")
    op.create_check_constraint(
        "ck_debate_topics_status",
        "debate_topics",
        "status IN ('scheduled', 'open', 'in_progress', 'closed')",
    )


def downgrade() -> None:
    op.execute("ALTER TABLE debate_topics DROP CONSTRAINT IF EXISTS ck_debate_topics_status")
    op.create_check_constraint(
        "ck_debate_topics_status",
        "debate_topics",
        "status IN ('open', 'in_progress', 'closed')",
    )
    op.drop_index("idx_debate_topics_schedule", table_name="debate_topics")
    op.drop_column("debate_topics", "is_admin_topic")
    op.drop_column("debate_topics", "scheduled_end_at")
    op.drop_column("debate_topics", "scheduled_start_at")
