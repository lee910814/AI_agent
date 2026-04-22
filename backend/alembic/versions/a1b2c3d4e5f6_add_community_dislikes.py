"""add community dislikes

Revision ID: a1b2c3d4e5f6
Revises: q8r9s0t1u2v3
Create Date: 2026-03-23

- community_posts.dislikes_count 컬럼 추가
- community_post_dislikes 테이블 추가
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "community_posts",
        sa.Column("dislikes_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "community_post_dislikes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("post_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("post_id", "user_id", name="uq_community_post_dislikes_post_user"),
    )
    op.create_index("idx_community_post_dislikes_post_id", "community_post_dislikes", ["post_id"])


def downgrade() -> None:
    op.drop_index("idx_community_post_dislikes_post_id", "community_post_dislikes")
    op.drop_table("community_post_dislikes")
    op.drop_column("community_posts", "dislikes_count")
