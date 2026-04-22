"""add match predictions table

기능 5: 매치 예측 투표 — debate_match_predictions 테이블 추가.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f8
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "debate_match_predictions",
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
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prediction", sa.String(10), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "prediction IN ('a_win', 'b_win', 'draw')",
            name="ck_debate_match_predictions_prediction",
        ),
        sa.UniqueConstraint("match_id", "user_id", name="uq_predictions_match_user"),
    )
    op.create_index(
        "idx_predictions_match",
        "debate_match_predictions",
        ["match_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_predictions_match", table_name="debate_match_predictions")
    op.drop_table("debate_match_predictions")
