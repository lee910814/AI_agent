"""add_platform_agent

Revision ID: p6k7l8m9n0o5
Revises: o5j6k7l8m9n4
Create Date: 2026-02-24 12:00:00.000000

debate_agents에 is_platform 컬럼 추가.
- is_platform: 관리자가 생성한 플랫폼 에이전트 여부 (기본값 false)
  플랫폼 에이전트는 자동 매칭 타임아웃 시 상대로 배정되며, 여러 매치에 동시 참여 가능.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p6k7l8m9n0o5"
down_revision: Union[str, None] = "o5j6k7l8m9n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS: 수동으로 컬럼이 이미 추가된 환경에서도 안전하게 실행
    op.execute(
        "ALTER TABLE debate_agents ADD COLUMN IF NOT EXISTS is_platform BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.drop_column("debate_agents", "is_platform")
