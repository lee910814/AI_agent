"""add user_follows and user_notifications tables

팔로우 & 알림 시스템:
- user_follows: 사용자가 다른 사용자 또는 에이전트를 팔로우하는 다형성 관계
- user_notifications: 매치 이벤트, 예측 결과, 팔로워 알림 수신함

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. user_follows 테이블 생성
    op.create_table(
        "user_follows",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), nullable=False),
        # 다형성 타겟: FK 없이 UUID만 저장 ('user' | 'agent')
        sa.Column("target_type", sa.String(10), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "target_type IN ('user', 'agent')",
            name="ck_user_follows_target_type",
        ),
        sa.UniqueConstraint(
            "follower_id", "target_type", "target_id",
            name="uq_user_follows_follower_target",
        ),
    )
    # 팔로워 수 카운트용: 특정 대상의 팔로워 집계
    op.create_index("idx_user_follows_target", "user_follows", ["target_type", "target_id"])
    # 내 팔로우 목록 조회용
    op.create_index("idx_user_follows_follower", "user_follows", ["follower_id"])

    # 2. user_notifications 테이블 생성
    op.create_table(
        "user_notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.String(500), nullable=True),
        sa.Column("link", sa.String(300), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    # 미읽기 알림 목록 조회: user_id + is_read 필터 후 최신순 정렬
    op.create_index(
        "idx_user_notifications_user_unread",
        "user_notifications",
        ["user_id", "is_read", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_user_notifications_user_unread", table_name="user_notifications")
    op.drop_table("user_notifications")

    op.drop_index("idx_user_follows_follower", table_name="user_follows")
    op.drop_index("idx_user_follows_target", table_name="user_follows")
    op.drop_table("user_follows")
