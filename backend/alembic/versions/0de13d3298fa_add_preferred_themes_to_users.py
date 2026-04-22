"""add_preferred_themes_to_users

Revision ID: 0de13d3298fa
Revises: l3m4n5o6p7q8
Create Date: 2026-03-17 01:09:24.524666
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0de13d3298fa'
down_revision: Union[str, None] = 'l3m4n5o6p7q8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('preferred_themes', postgresql.ARRAY(sa.String(length=30)), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'preferred_themes')
