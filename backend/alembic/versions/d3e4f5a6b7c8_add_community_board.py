"""add_community_board

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-02-15 14:00:00.000000

커뮤니티 게시판(캐릭터 라운지) 테이블 추가.
boards, board_posts, board_comments, board_reactions 4개 테이블.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- boards ---
    op.create_table(
        "boards",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("board_key", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("age_rating", sa.String(20), nullable=False, server_default="all"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("board_key"),
        sa.CheckConstraint("age_rating IN ('all', '15+', '18+')", name="ck_boards_age_rating"),
    )

    # 초기 게시판 데이터
    op.execute("""
        INSERT INTO boards (board_key, display_name, description, age_rating, sort_order) VALUES
        ('free', '자유 게시판', '자유롭게 이야기를 나누세요', 'all', 1),
        ('webtoon_review', '웹툰 리뷰', '웹툰 회차별 리뷰를 공유하세요', 'all', 2),
        ('character_chat', '캐릭터 잡담', 'AI 캐릭터들의 일상 이야기', 'all', 3)
    """)

    # --- board_posts ---
    op.create_table(
        "board_posts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("board_id", sa.UUID(), nullable=False),
        sa.Column("author_user_id", sa.UUID(), nullable=True),
        sa.Column("author_persona_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("age_rating", sa.String(20), nullable=False, server_default="all"),
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["author_persona_id"], ["personas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("author_user_id IS NOT NULL OR author_persona_id IS NOT NULL", name="ck_post_author"),
        sa.CheckConstraint("age_rating IN ('all', '15+', '18+')", name="ck_post_age_rating"),
    )
    op.create_index("idx_posts_board", "board_posts", ["board_id", "created_at"])
    op.create_index("idx_posts_persona", "board_posts", ["author_persona_id", "created_at"])
    op.create_index("idx_posts_user", "board_posts", ["author_user_id", "created_at"])

    # --- board_comments ---
    op.create_table(
        "board_comments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("author_user_id", sa.UUID(), nullable=True),
        sa.Column("author_persona_id", sa.UUID(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["board_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["board_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["author_persona_id"], ["personas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("author_user_id IS NOT NULL OR author_persona_id IS NOT NULL", name="ck_comment_author"),
    )
    op.create_index("idx_comments_post", "board_comments", ["post_id", "created_at"])
    op.create_index("idx_comments_parent", "board_comments", ["parent_id"])

    # --- board_reactions ---
    op.create_table(
        "board_reactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=True),
        sa.Column("comment_id", sa.UUID(), nullable=True),
        sa.Column("reaction_type", sa.String(20), nullable=False, server_default="like"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["board_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["comment_id"], ["board_comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(post_id IS NOT NULL AND comment_id IS NULL) OR (post_id IS NULL AND comment_id IS NOT NULL)",
            name="ck_reaction_target",
        ),
        sa.UniqueConstraint("user_id", "post_id", name="uq_reaction_post"),
        sa.UniqueConstraint("user_id", "comment_id", name="uq_reaction_comment"),
    )


def downgrade() -> None:
    op.drop_table("board_reactions")
    op.drop_index("idx_comments_parent", table_name="board_comments")
    op.drop_index("idx_comments_post", table_name="board_comments")
    op.drop_table("board_comments")
    op.drop_index("idx_posts_user", table_name="board_posts")
    op.drop_index("idx_posts_persona", table_name="board_posts")
    op.drop_index("idx_posts_board", table_name="board_posts")
    op.drop_table("board_posts")
    op.drop_table("boards")
