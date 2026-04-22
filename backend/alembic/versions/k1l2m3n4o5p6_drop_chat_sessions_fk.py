"""Drop chat_sessions FK from token_usage_logs.session_id

chat_sessions 테이블은 챗봇 프로젝트 산물로 토론 플랫폼 DB에 존재하지 않음.
ForeignKey 참조가 SQLAlchemy 매퍼 오류를 유발해 토론 엔진이 크래시되는 문제 수정.

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-03-06

"""

from alembic import op

revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # chat_sessions FK 제약이 존재할 경우에만 삭제 (idempotent)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_type = 'FOREIGN KEY'
                  AND table_name = 'token_usage_logs'
                  AND constraint_name LIKE '%chat_session%'
            ) THEN
                ALTER TABLE token_usage_logs
                    DROP CONSTRAINT IF EXISTS token_usage_logs_session_id_fkey;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    # chat_sessions 테이블이 없으므로 FK 복구 불가 — 무시
    pass
