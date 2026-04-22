"""add season system tables

기능 8: 시즌 시스템 — debate_seasons, debate_season_results 테이블 추가.

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4e5f6g7h8i9"
down_revision = "c3d4e5f6g7h8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "debate_seasons",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("season_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="upcoming"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('upcoming', 'active', 'completed')",
            name="ck_debate_seasons_status",
        ),
    )

    op.create_table(
        "debate_season_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("final_elo", sa.Integer(), nullable=False),
        sa.Column("final_tier", sa.String(20), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("reward_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("season_id", "agent_id", name="uq_season_results_season_agent"),
    )
    op.create_index("idx_season_results_season", "debate_season_results", ["season_id"])


def downgrade() -> None:
    op.drop_index("idx_season_results_season", table_name="debate_season_results")
    op.drop_table("debate_season_results")
    op.drop_table("debate_seasons")
