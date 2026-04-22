"""add_persona_anonymous

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-18 00:00:00.000000

페르소나에 is_anonymous 컬럼 추가 (생성자 닉네임 비공개 옵션).
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("personas", sa.Column("is_anonymous", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("personas", "is_anonymous")
