"""add_agent_system

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-02-15 16:00:00.000000

AI 에이전트 자동 활동 테이블 추가.
persona_lounge_configs, agent_activity_logs 2개 테이블.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- persona_lounge_configs ---
    op.create_table(
        "persona_lounge_configs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("activity_level", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("interest_tags", sa.ARRAY(sa.String()), server_default="{}"),
        sa.Column("allowed_boards", sa.ARRAY(sa.UUID()), server_default="{}"),
        sa.Column("daily_action_limit", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("actions_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("persona_id"),
        sa.CheckConstraint("activity_level IN ('quiet', 'normal', 'active')", name="ck_lounge_activity"),
    )

    # --- agent_activity_logs ---
    op.create_table(
        "agent_activity_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("target_post_id", sa.UUID(), nullable=True),
        sa.Column("target_comment_id", sa.UUID(), nullable=True),
        sa.Column("result_post_id", sa.UUID(), nullable=True),
        sa.Column("result_comment_id", sa.UUID(), nullable=True),
        sa.Column("llm_model_id", sa.UUID(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_post_id"], ["board_posts.id"]),
        sa.ForeignKeyConstraint(["target_comment_id"], ["board_comments.id"]),
        sa.ForeignKeyConstraint(["result_post_id"], ["board_posts.id"]),
        sa.ForeignKeyConstraint(["result_comment_id"], ["board_comments.id"]),
        sa.ForeignKeyConstraint(["llm_model_id"], ["llm_models.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agent_log_persona", "agent_activity_logs", ["persona_id", "created_at"])
    op.create_index("idx_agent_log_user", "agent_activity_logs", ["owner_user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_agent_log_user", table_name="agent_activity_logs")
    op.drop_index("idx_agent_log_persona", table_name="agent_activity_logs")
    op.drop_table("agent_activity_logs")
    op.drop_table("persona_lounge_configs")
