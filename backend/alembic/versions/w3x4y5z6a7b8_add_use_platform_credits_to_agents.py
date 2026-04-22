"""debate_agents에 use_platform_credits 컬럼 추가

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-02-26

플랫폼 크레딧으로 API 비용을 지불하는 에이전트 지원 (BYOK API 키 불필요)
"""

from alembic import op
import sqlalchemy as sa

revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "debate_agents",
        sa.Column(
            "use_platform_credits",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("debate_agents", "use_platform_credits")
