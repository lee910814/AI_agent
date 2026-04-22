"""add_topic_tools_enabled

Revision ID: o5j6k7l8m9n4
Revises: n4i5j6k7l8m9
Create Date: 2026-02-24 11:00:00.000000

debate_topics에 tools_enabled 컬럼 추가.
- tools_enabled: 툴 사용 허용 여부 (기본값 true)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "o5j6k7l8m9n4"
down_revision: Union[str, None] = "n4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "debate_topics",
        sa.Column("tools_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("debate_topics", "tools_enabled")
