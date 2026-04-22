"""add video_generations table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-19 00:00:00.000000

LTX-Video 13B 영상 생성 작업 추적 테이블 추가.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "video_generations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False, server_default="768"),
        sa.Column("height", sa.Integer(), nullable=False, server_default="512"),
        sa.Column("num_frames", sa.Integer(), nullable=False, server_default="97"),
        sa.Column("frame_rate", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("num_inference_steps", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("guidance_scale", sa.Numeric(4, 2), nullable=False, server_default="3.0"),
        sa.Column("seed", sa.BigInteger(), nullable=True),
        sa.Column("model_variant", sa.String(20), nullable=False, server_default="dev"),
        sa.Column("keyframes", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("runpod_job_id", sa.String(100), nullable=True),
        sa.Column("result_video_url", sa.String(500), nullable=True),
        sa.Column("result_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'submitted', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_video_gen_status",
        ),
        sa.CheckConstraint("model_variant IN ('dev', 'distilled')", name="ck_video_gen_variant"),
        sa.CheckConstraint("(num_frames - 1) % 8 = 0 AND num_frames >= 9", name="ck_video_gen_frames"),
    )
    op.create_index("idx_video_gen_user", "video_generations", ["created_by", sa.text("created_at DESC")])
    op.create_index(
        "idx_video_gen_active_status",
        "video_generations",
        ["status"],
        postgresql_where=sa.text("status NOT IN ('completed', 'failed', 'cancelled')"),
    )


def downgrade() -> None:
    op.drop_index("idx_video_gen_active_status", table_name="video_generations")
    op.drop_index("idx_video_gen_user", table_name="video_generations")
    op.drop_table("video_generations")
