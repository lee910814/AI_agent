"""add llm_model tier and credit_per_1k_tokens

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-15 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'llm_models' AND column_name = 'tier'"
        )
    )
    if not result.fetchone():
        op.add_column(
            "llm_models",
            sa.Column("tier", sa.String(20), nullable=False, server_default="economy"),
        )

    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'llm_models' AND column_name = 'credit_per_1k_tokens'"
        )
    )
    if not result.fetchone():
        op.add_column(
            "llm_models",
            sa.Column("credit_per_1k_tokens", sa.Integer(), nullable=False, server_default="1"),
        )

    result = conn.execute(
        sa.text(
            "SELECT conname FROM pg_constraint "
            "WHERE conname = 'ck_llm_tier'"
        )
    )
    if not result.fetchone():
        op.create_check_constraint(
            "ck_llm_tier",
            "llm_models",
            "tier IN ('economy', 'standard', 'premium')",
        )


def downgrade() -> None:
    op.drop_constraint("ck_llm_tier", "llm_models", type_="check")
    op.drop_column("llm_models", "credit_per_1k_tokens")
    op.drop_column("llm_models", "tier")
