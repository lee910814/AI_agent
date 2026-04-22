"""users 테이블에 login_id 컬럼 추가

로그인 전용 식별자(login_id)를 분리. 닉네임은 표시명으로만 사용하고,
로그인은 영문/숫자/밑줄로만 구성된 login_id 기반으로 변경.

Revision ID: t0o1p2q3r4s5
Revises: s9n0o1p2q3r4
Create Date: 2026-02-26
"""
import sqlalchemy as sa
from alembic import op

revision = "t0o1p2q3r4s5"
down_revision = "s9n0o1p2q3r4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 nickname 값을 login_id로 초기화 (30자 제한 준수)
    op.add_column("users", sa.Column("login_id", sa.String(30), nullable=True))
    op.execute("UPDATE users SET login_id = SUBSTRING(nickname, 1, 30)")
    op.alter_column("users", "login_id", nullable=False)
    op.create_unique_constraint("uq_users_login_id", "users", ["login_id"])
    op.create_index("idx_users_login_id", "users", ["login_id"])


def downgrade() -> None:
    op.drop_index("idx_users_login_id", table_name="users")
    op.drop_constraint("uq_users_login_id", "users", type_="unique")
    op.drop_column("users", "login_id")
