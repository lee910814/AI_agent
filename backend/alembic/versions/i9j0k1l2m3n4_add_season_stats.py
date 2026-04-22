"""add debate_agent_season_stats + debate_matches.season_id

시즌별 독립 ELO/전적 추적:
- debate_agent_season_stats 테이블 신규 생성 (에이전트 × 시즌 단위 ELO/전적)
- debate_matches.season_id FK 추가 (활성 시즌 매치 자동 태깅)

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. debate_agent_season_stats 테이블 생성
    op.create_table(
        "debate_agent_season_stats",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("season_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("elo_rating", sa.Integer(), server_default="1500", nullable=False),
        sa.Column("tier", sa.String(20), server_default="Iron", nullable=False),
        sa.Column("wins", sa.Integer(), server_default="0", nullable=False),
        sa.Column("losses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("draws", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["debate_agents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["season_id"], ["debate_seasons.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("agent_id", "season_id", name="uq_season_stats_agent_season"),
    )
    op.create_index(
        "idx_season_stats_season_elo",
        "debate_agent_season_stats",
        ["season_id", "elo_rating"],
    )
    op.create_index(
        "idx_season_stats_agent",
        "debate_agent_season_stats",
        ["agent_id"],
    )

    # 2. debate_matches.season_id 컬럼 추가
    op.add_column(
        "debate_matches",
        sa.Column("season_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_debate_matches_season",
        "debate_matches",
        "debate_seasons",
        ["season_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_debate_matches_season",
        "debate_matches",
        ["season_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_debate_matches_season", table_name="debate_matches")
    op.drop_constraint("fk_debate_matches_season", "debate_matches", type_="foreignkey")
    op.drop_column("debate_matches", "season_id")

    op.drop_index("idx_season_stats_agent", table_name="debate_agent_season_stats")
    op.drop_index("idx_season_stats_season_elo", table_name="debate_agent_season_stats")
    op.drop_table("debate_agent_season_stats")
