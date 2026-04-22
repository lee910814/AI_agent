"""debate_matches에 is_test 컬럼 추가

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-02-26

관리자 force-match(테스트 매치)를 일반 매치와 구분하기 위한 플래그.
is_test=True인 매치는 항상 플랫폼 API 키를 사용하고 ELO 랭킹에 미반영.
"""

from alembic import op
import sqlalchemy as sa

revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "debate_matches",
        sa.Column(
            "is_test",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("debate_matches", "is_test")
