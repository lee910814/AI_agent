"""add_banned_until

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-20 01:00:00.000000

사용자 기간 밴 지원을 위해 users 테이블에 banned_until 컬럼 추가.
NULL이면 밴 아님, 값이 있으면 해당 시각까지 밴 적용.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_users_banned_until", "users", ["banned_until"])


def downgrade() -> None:
    op.drop_index("idx_users_banned_until", table_name="users")
    op.drop_column("users", "banned_until")
