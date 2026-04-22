"""add promotion series system

승급전/강등전 시리즈 시스템:
- debate_promotion_series 테이블 신규 생성
- debate_agents.active_series_id FK 추가
- debate_matches.match_type / series_id 컬럼 추가

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "h8i9j0k1l2m3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. debate_promotion_series 테이블 생성
    op.create_table(
        "debate_promotion_series",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("series_type", sa.String(20), nullable=False),
        sa.Column("from_tier", sa.String(20), nullable=False),
        sa.Column("to_tier", sa.String(20), nullable=False),
        sa.Column("required_wins", sa.Integer(), nullable=False),
        sa.Column("current_wins", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_losses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["debate_agents.id"], ondelete="CASCADE"),
        sa.CheckConstraint("series_type IN ('promotion', 'demotion')", name="ck_promotion_series_type"),
        sa.CheckConstraint("status IN ('active', 'won', 'lost', 'cancelled')", name="ck_promotion_series_status"),
    )
    op.create_index(
        "idx_promotion_series_agent_status",
        "debate_promotion_series",
        ["agent_id", "status"],
    )

    # 2. debate_agents.active_series_id 추가
    op.add_column(
        "debate_agents",
        sa.Column("active_series_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_debate_agents_active_series",
        "debate_agents",
        "debate_promotion_series",
        ["active_series_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. debate_matches.match_type / series_id 추가
    op.add_column(
        "debate_matches",
        sa.Column("match_type", sa.String(20), server_default="ranked", nullable=False),
    )
    op.add_column(
        "debate_matches",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_debate_matches_series",
        "debate_matches",
        "debate_promotion_series",
        ["series_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_debate_matches_match_type",
        "debate_matches",
        "match_type IN ('ranked', 'promotion', 'demotion')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_debate_matches_match_type", "debate_matches", type_="check")
    op.drop_constraint("fk_debate_matches_series", "debate_matches", type_="foreignkey")
    op.drop_column("debate_matches", "series_id")
    op.drop_column("debate_matches", "match_type")

    op.drop_constraint("fk_debate_agents_active_series", "debate_agents", type_="foreignkey")
    op.drop_column("debate_agents", "active_series_id")

    op.drop_index("idx_promotion_series_agent_status", table_name="debate_promotion_series")
    op.drop_table("debate_promotion_series")
