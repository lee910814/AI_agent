"""debate_match_queue에 is_ready 컬럼 추가 (준비 완료 버튼 시스템)

Revision ID: u1v2w3x4y5z6
Revises: t0o1p2q3r4s5
Create Date: 2026-02-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, None] = "t0o1p2q3r4s5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "debate_match_queue",
        sa.Column("is_ready", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("debate_match_queue", "is_ready")
