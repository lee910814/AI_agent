"""debate_agents 티어/프로필공개, debate_topics 비밀번호방, debate_matches ELO 변동 추적

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-02-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v2w3x4y5z6a7"
down_revision: Union[str, None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # debate_agents: 티어 + 프로필 공개
    op.add_column(
        "debate_agents",
        sa.Column("tier", sa.String(20), nullable=False, server_default="Iron"),
    )
    op.add_column(
        "debate_agents",
        sa.Column("tier_protection_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "debate_agents",
        sa.Column("is_profile_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # debate_topics: 비밀번호 방
    op.add_column(
        "debate_topics",
        sa.Column("is_password_protected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "debate_topics",
        sa.Column("password_hash", sa.String(255), nullable=True),
    )

    # debate_matches: ELO 변동 기록
    op.add_column(
        "debate_matches",
        sa.Column("elo_a_before", sa.Integer(), nullable=True),
    )
    op.add_column(
        "debate_matches",
        sa.Column("elo_b_before", sa.Integer(), nullable=True),
    )
    op.add_column(
        "debate_matches",
        sa.Column("elo_a_after", sa.Integer(), nullable=True),
    )
    op.add_column(
        "debate_matches",
        sa.Column("elo_b_after", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("debate_matches", "elo_b_after")
    op.drop_column("debate_matches", "elo_a_after")
    op.drop_column("debate_matches", "elo_b_before")
    op.drop_column("debate_matches", "elo_a_before")
    op.drop_column("debate_topics", "password_hash")
    op.drop_column("debate_topics", "is_password_protected")
    op.drop_column("debate_agents", "is_profile_public")
    op.drop_column("debate_agents", "tier_protection_count")
    op.drop_column("debate_agents", "tier")
