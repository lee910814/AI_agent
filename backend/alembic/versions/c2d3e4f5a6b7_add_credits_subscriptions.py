"""add_credits_subscriptions

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-02-15 12:00:00.000000

대화석 크레딧 시스템 + 구독 플랜 테이블 추가.
기존 users 테이블에 credit_balance, last_credit_grant_at 컬럼 추가.
기존 llm_models 테이블에 tier 컬럼 추가.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- subscription_plans ---
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plan_key", sa.String(30), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("price_krw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_credits", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("credit_rollover_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_lounge_personas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_agent_actions", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_key"),
    )

    # 초기 플랜 데이터
    op.execute("""
        INSERT INTO subscription_plans (plan_key, display_name, price_krw, daily_credits, credit_rollover_days, max_lounge_personas, max_agent_actions, features) VALUES
        ('free', '무료', 0, 50, 0, 1, 5, '{"notifications": false, "reports": false}'),
        ('premium', '프리미엄', 6900, 300, 30, 5, 30, '{"notifications": true, "reports": true}')
    """)

    # --- user_subscriptions ---
    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('active', 'cancelled', 'expired')", name="ck_subscription_status"),
    )
    op.create_index("idx_sub_user", "user_subscriptions", ["user_id", "status"])

    # --- credit_ledger ---
    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("tx_type", sa.String(30), nullable=False),
        sa.Column("reference_id", sa.String(100), nullable=True),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "tx_type IN ('daily_grant','purchase','chat','lounge_post','lounge_comment','review','agent_action','expire','admin_grant','refund')",
            name="ck_ledger_tx_type",
        ),
    )
    op.create_index("idx_ledger_user", "credit_ledger", ["user_id", "created_at"])

    # --- credit_costs ---
    op.create_table(
        "credit_costs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("model_tier", sa.String(20), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action", "model_tier", name="uq_credit_cost"),
    )

    # 초기 소비 단가
    op.execute("""
        INSERT INTO credit_costs (action, model_tier, cost) VALUES
        ('chat', 'economy', 1), ('chat', 'standard', 3), ('chat', 'premium', 5),
        ('lounge_comment', 'economy', 1), ('lounge_comment', 'standard', 2), ('lounge_comment', 'premium', 3),
        ('lounge_post', 'economy', 2), ('lounge_post', 'standard', 4), ('lounge_post', 'premium', 6),
        ('review', 'economy', 3), ('review', 'standard', 8), ('review', 'premium', 12),
        ('agent_action', 'economy', 1), ('agent_action', 'standard', 2), ('agent_action', 'premium', 3)
    """)

    # --- users 테이블 컬럼 추가 ---
    op.add_column("users", sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("last_credit_grant_at", sa.DateTime(timezone=True), nullable=True))

    # --- llm_models 테이블 컬럼 추가 ---
    op.add_column("llm_models", sa.Column("tier", sa.String(20), nullable=False, server_default="economy"))
    op.create_check_constraint("ck_llm_tier", "llm_models", "tier IN ('economy', 'standard', 'premium')")


def downgrade() -> None:
    op.drop_constraint("ck_llm_tier", "llm_models", type_="check")
    op.drop_column("llm_models", "tier")
    op.drop_column("users", "last_credit_grant_at")
    op.drop_column("users", "credit_balance")
    op.drop_table("credit_costs")
    op.drop_index("idx_ledger_user", table_name="credit_ledger")
    op.drop_table("credit_ledger")
    op.drop_index("idx_sub_user", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")
    op.drop_table("subscription_plans")
