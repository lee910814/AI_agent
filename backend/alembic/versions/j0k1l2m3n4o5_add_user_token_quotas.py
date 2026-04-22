"""add user token quotas

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa

revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("daily_token_limit", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("monthly_token_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "monthly_token_limit")
    op.drop_column("users", "daily_token_limit")
