"""add_persona_reports

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-20 00:00:00.000000

페르소나 신고 테이블 추가.
사용자가 부적절한 페르소나를 신고하고 관리자가 검토/처리할 수 있는 구조.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "persona_reports",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "reason IN ('inappropriate', 'sexual', 'harassment', 'copyright', 'spam', 'other')",
            name="ck_persona_reports_reason",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'reviewed', 'dismissed')",
            name="ck_persona_reports_status",
        ),
        sa.UniqueConstraint("persona_id", "reporter_id", name="uq_persona_report_unique"),
    )
    op.create_index("idx_persona_reports_status", "persona_reports", ["status"])
    op.create_index("idx_persona_reports_persona_id", "persona_reports", ["persona_id"])


def downgrade() -> None:
    op.drop_index("idx_persona_reports_persona_id", table_name="persona_reports")
    op.drop_index("idx_persona_reports_status", table_name="persona_reports")
    op.drop_table("persona_reports")
