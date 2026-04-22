"""add_human_detection

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-02-23 15:00:00.000000

debate_turn_logs에 휴먼 감지 관련 컬럼 추가.
- human_suspicion_score: 다층 감지 의심 점수 (0~100)
- response_time_ms: 턴 요청~응답 시간 (밀리초)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "m3h4i5j6k7l8"
down_revision: Union[str, None] = "l2g3h4i5j6k7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "debate_turn_logs",
        sa.Column("human_suspicion_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "debate_turn_logs",
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("debate_turn_logs", "response_time_ms")
    op.drop_column("debate_turn_logs", "human_suspicion_score")
