"""add_match_id_to_token_usage_logs

Revision ID: s0t1u2v3w4x5
Revises: q8r9s0t1u2v3
Create Date: 2026-03-30 00:00:00.000000

모니터링 시 어떤 토론 매치의 LLM 호출인지 추적할 수 있도록
token_usage_logs에 match_id(FK → debate_matches) 컬럼을 추가한다.
토론 외 LLM 호출(BYOK 등)은 NULL로 유지된다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "s0t1u2v3w4x5"
down_revision: Union[str, None] = "q8r9s0t1u2v3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE token_usage_logs
        ADD COLUMN IF NOT EXISTS match_id UUID
            REFERENCES debate_matches(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_match
        ON token_usage_logs (match_id)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_usage_match")
    op.execute("ALTER TABLE token_usage_logs DROP COLUMN IF EXISTS match_id")
