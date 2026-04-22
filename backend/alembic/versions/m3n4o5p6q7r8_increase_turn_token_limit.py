"""increase turn_token_limit default from 500 to 1500

기존 토론 토픽의 턴 토큰 한도가 500으로 너무 낮아 에이전트 발언이 잘리는 문제.
1500으로 상향해 자연스러운 발언 길이를 허용.

Revision ID: m3n4o5p6q7r8
Revises: i9j0k1l2m3n4
Create Date: 2026-03-10
"""

from alembic import op

revision = "m3n4o5p6q7r8"
down_revision = "l2m3n4o5p6q7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기본값 500으로 생성된 기존 행을 1500으로 일괄 업데이트
    op.execute(
        "UPDATE debate_topics SET turn_token_limit = 1500 WHERE turn_token_limit = 500"
    )
    # 컬럼 DEFAULT를 1500으로 변경
    op.execute(
        "ALTER TABLE debate_topics ALTER COLUMN turn_token_limit SET DEFAULT 1500"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE debate_topics SET turn_token_limit = 500 WHERE turn_token_limit = 1500"
    )
    op.execute(
        "ALTER TABLE debate_topics ALTER COLUMN turn_token_limit SET DEFAULT 500"
    )
