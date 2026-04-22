"""add_character_page_credit_costs

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-02-21 12:00:00.000000

캐릭터 페이지 시스템 신규 액션 크레딧 비용 시드 데이터.
- character_post: 2 credits (economy)
- character_comment: 1 credit (economy)
- character_chat_turn: 3 credits (economy)
"""

from alembic import op

revision = "i9d0e1f2g3h4"
down_revision = "h8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 캐릭터 페이지 관련 크레딧 비용 시드
    op.execute("""
        INSERT INTO credit_costs (id, action, model_tier, cost)
        VALUES
            (gen_random_uuid(), 'character_post', 'economy', 2),
            (gen_random_uuid(), 'character_comment', 'economy', 1),
            (gen_random_uuid(), 'character_chat_turn', 'economy', 3)
        ON CONFLICT (action, model_tier) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM credit_costs
        WHERE action IN ('character_post', 'character_comment', 'character_chat_turn')
    """)
