"""add_community_posts

Revision ID: p7q8r9s0t1u2
Revises: 0de13d3298fa
Create Date: 2026-03-18 00:00:00.000000

커뮤니티 피드 포스트 테이블 추가.
- community_posts: 에이전트 매치 소감 포스트
- community_post_likes: 사용자 좋아요
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p7q8r9s0t1u2"
down_revision: Union[str, None] = "0de13d3298fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "community_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("debate_matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("match_result", postgresql.JSONB, nullable=True),
        sa.Column("likes_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_community_posts_created_at", "community_posts", ["created_at"])
    op.create_index("idx_community_posts_agent_id", "community_posts", ["agent_id"])

    op.create_table(
        "community_post_likes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("community_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("post_id", "user_id", name="uq_community_post_likes_post_user"),
    )
    op.create_index("idx_community_post_likes_post_id", "community_post_likes", ["post_id"])
    op.create_index("idx_community_post_likes_user_id", "community_post_likes", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_community_post_likes_user_id", table_name="community_post_likes")
    op.drop_index("idx_community_post_likes_post_id", table_name="community_post_likes")
    op.drop_table("community_post_likes")
    op.drop_index("idx_community_posts_agent_id", table_name="community_posts")
    op.drop_index("idx_community_posts_created_at", table_name="community_posts")
    op.drop_table("community_posts")
