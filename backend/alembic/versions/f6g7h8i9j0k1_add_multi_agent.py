"""add multi-agent format support

기능 10: 멀티 에이전트 패널 토론 — debate_matches.format 컬럼, debate_match_participants 테이블 추가.

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6g7h8i9j0k1"
down_revision = "e5f6g7h8i9j0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "debate_matches",
        sa.Column("format", sa.String(10), nullable=False, server_default="1v1"),
    )

    op.create_table(
        "debate_match_participants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_agent_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("team", sa.String(1), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.CheckConstraint("team IN ('A', 'B')", name="ck_debate_match_participants_team"),
        sa.UniqueConstraint("match_id", "team", "slot", name="uq_match_participants_team_slot"),
    )
    op.create_index("idx_match_participants_match", "debate_match_participants", ["match_id"])


def downgrade() -> None:
    op.drop_index("idx_match_participants_match", table_name="debate_match_participants")
    op.drop_table("debate_match_participants")
    op.drop_column("debate_matches", "format")
