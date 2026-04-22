"""add draw_count to debate_promotion_series + expired status

debate_promotion_series.draw_count 컬럼 추가:
- 시리즈 내 무승부 횟수 추적
- debate_series_max_draws(기본 3회) 초과 시 'expired'로 자동 만료

status CHECK 제약조건에 'expired' 추가.

Revision ID: k2l3m4n5o6p7
Revises: j0k1l2m3n4o5
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "k2l3m4n5o6p7"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # draw_count 컬럼 추가 (기존 행은 0으로 채움)
    op.add_column(
        "debate_promotion_series",
        sa.Column("draw_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # 기존 CHECK 제약조건 삭제 후 'expired' 포함한 새 제약조건으로 교체
    op.drop_constraint("ck_promotion_series_status", "debate_promotion_series", type_="check")
    op.create_check_constraint(
        "ck_promotion_series_status",
        "debate_promotion_series",
        "status IN ('active', 'won', 'lost', 'cancelled', 'expired')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_promotion_series_status", "debate_promotion_series", type_="check")
    op.create_check_constraint(
        "ck_promotion_series_status",
        "debate_promotion_series",
        "status IN ('active', 'won', 'lost', 'cancelled')",
    )
    op.drop_column("debate_promotion_series", "draw_count")
