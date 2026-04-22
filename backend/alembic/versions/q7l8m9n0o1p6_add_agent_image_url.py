"""add_agent_image_url

Revision ID: q7l8m9n0o1p6
Revises: p6k7l8m9n0o5
Create Date: 2026-02-25 12:00:00.000000

debate_agents에 image_url 컬럼 추가.
- image_url: 에이전트 프로필 이미지 경로 (nullable)
  /api/uploads/image 엔드포인트로 업로드한 이미지 URL을 저장.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q7l8m9n0o1p6"
down_revision: Union[str, None] = "p6k7l8m9n0o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "debate_agents",
        sa.Column("image_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("debate_agents", "image_url")
