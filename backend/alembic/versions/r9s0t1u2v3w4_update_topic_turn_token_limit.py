"""update_topic_turn_token_limit

Revision ID: r9s0t1u2v3w4
Revises: a1b2c3d4e5f6
Create Date: 2026-03-24 00:00:00.000000

기존 토픽의 turn_token_limit이 800 미만인 레코드를 800으로 상향.
server_default는 이미 2000이므로 신규 토픽에는 영향 없음.
"""

from alembic import op

revision = "r9s0t1u2v3w4"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE debate_topics SET turn_token_limit = 800 WHERE turn_token_limit < 800")


def downgrade() -> None:
    op.execute("UPDATE debate_topics SET turn_token_limit = 500 WHERE turn_token_limit = 800")
