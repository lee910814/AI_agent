"""add tournament system tables

기능 9: 토너먼트 시스템 — debate_tournaments, debate_tournament_entries 테이블 추가.
debate_matches에 tournament_id, tournament_round 컬럼 추가.

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5f6g7h8i9j0"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "debate_tournaments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="registration"),
        sa.Column("bracket_size", sa.Integer(), nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "winner_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('registration', 'in_progress', 'completed', 'cancelled')",
            name="ck_debate_tournaments_status",
        ),
        sa.CheckConstraint(
            "bracket_size IN (4, 8, 16)",
            name="ck_debate_tournaments_bracket_size",
        ),
    )

    op.create_table(
        "debate_tournament_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tournament_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_tournaments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("eliminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eliminated_round", sa.Integer(), nullable=True),
        sa.UniqueConstraint("tournament_id", "agent_id", name="uq_tournament_entries_agent"),
        sa.UniqueConstraint("tournament_id", "seed", name="uq_tournament_entries_seed"),
    )
    op.create_index("idx_tournament_entries_tournament", "debate_tournament_entries", ["tournament_id"])

    op.add_column(
        "debate_matches",
        sa.Column(
            "tournament_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_tournaments.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "debate_matches",
        sa.Column("tournament_round", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("debate_matches", "tournament_round")
    op.drop_column("debate_matches", "tournament_id")
    op.drop_index("idx_tournament_entries_tournament", table_name="debate_tournament_entries")
    op.drop_table("debate_tournament_entries")
    op.drop_table("debate_tournaments")
