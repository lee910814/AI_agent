"""add_rp_features

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-02-15 20:00:00.000000

RP 챗봇 15대 기능 지원을 위한 DB 확장.
- personas: description, greeting_message, scenario, example_dialogues, tags, chat_count, like_count
- chat_sessions: title, is_pinned, user_persona_id
- chat_messages: parent_id, is_active, is_edited, edited_at
- user_personas (신규)
- persona_favorites (신규)
- persona_relationships (신규)
- notifications (신규)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1-D. user_personas (chat_sessions FK 대상이므로 먼저 생성) ──
    op.create_table(
        "user_personas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("is_default", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_user_personas_user", "user_personas", ["user_id"])

    # ── 1-A. personas 컬럼 추가 ──
    op.add_column("personas", sa.Column("description", sa.Text, nullable=True))
    op.add_column("personas", sa.Column("greeting_message", sa.Text, nullable=True))
    op.add_column("personas", sa.Column("scenario", sa.Text, nullable=True))
    op.add_column("personas", sa.Column("example_dialogues", JSONB, nullable=True))
    op.add_column("personas", sa.Column("tags", ARRAY(sa.String(30)), nullable=True))
    op.add_column("personas", sa.Column("chat_count", sa.Integer, server_default="0", nullable=False))
    op.add_column("personas", sa.Column("like_count", sa.Integer, server_default="0", nullable=False))

    # ── 1-B. chat_sessions 컬럼 추가 ──
    op.add_column("chat_sessions", sa.Column("title", sa.String(100), nullable=True))
    op.add_column("chat_sessions", sa.Column("is_pinned", sa.Boolean, server_default="false", nullable=False))
    op.add_column("chat_sessions", sa.Column("user_persona_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_sessions_user_persona",
        "chat_sessions",
        "user_personas",
        ["user_persona_id"],
        ["id"],
    )

    # ── 1-C. chat_messages 컬럼 추가 ──
    op.add_column("chat_messages", sa.Column("parent_id", sa.BigInteger, nullable=True))
    op.add_column("chat_messages", sa.Column("is_active", sa.Boolean, server_default="true", nullable=False))
    op.add_column("chat_messages", sa.Column("is_edited", sa.Boolean, server_default="false", nullable=False))
    op.add_column("chat_messages", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_messages_parent",
        "chat_messages",
        "chat_messages",
        ["parent_id"],
        ["id"],
    )
    op.create_index("idx_messages_parent", "chat_messages", ["parent_id"])

    # ── 1-E. persona_favorites ──
    op.create_table(
        "persona_favorites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("persona_id", UUID(as_uuid=True), sa.ForeignKey("personas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "persona_id", name="uq_favorite_user_persona"),
    )
    op.create_index("idx_favorites_user", "persona_favorites", ["user_id"])

    # ── 1-F. persona_relationships ──
    op.create_table(
        "persona_relationships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("persona_id", UUID(as_uuid=True), sa.ForeignKey("personas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("affection_level", sa.Integer, server_default="0", nullable=False),
        sa.Column("relationship_stage", sa.String(30), server_default="stranger", nullable=False),
        sa.Column("interaction_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "persona_id", name="uq_relationship_user_persona"),
        sa.CheckConstraint(
            "relationship_stage IN ('stranger','acquaintance','friend','close_friend','crush','lover','soulmate')",
            name="ck_relationship_stage",
        ),
        sa.CheckConstraint("affection_level BETWEEN 0 AND 1000", name="ck_affection_range"),
    )
    op.create_index("idx_relationships_user", "persona_relationships", ["user_id"])

    # ── 1-G. notifications ──
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("is_read", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "type IN ('persona_approved','persona_blocked','reply','system','relationship','credit')",
            name="ck_notification_type",
        ),
    )
    op.create_index("idx_notifications_user_unread", "notifications", ["user_id", "is_read"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("persona_relationships")
    op.drop_table("persona_favorites")

    op.drop_index("idx_messages_parent", table_name="chat_messages")
    op.drop_constraint("fk_messages_parent", "chat_messages", type_="foreignkey")
    op.drop_column("chat_messages", "edited_at")
    op.drop_column("chat_messages", "is_edited")
    op.drop_column("chat_messages", "is_active")
    op.drop_column("chat_messages", "parent_id")

    op.drop_constraint("fk_sessions_user_persona", "chat_sessions", type_="foreignkey")
    op.drop_column("chat_sessions", "user_persona_id")
    op.drop_column("chat_sessions", "is_pinned")
    op.drop_column("chat_sessions", "title")

    op.drop_column("personas", "like_count")
    op.drop_column("personas", "chat_count")
    op.drop_column("personas", "tags")
    op.drop_column("personas", "example_dialogues")
    op.drop_column("personas", "scenario")
    op.drop_column("personas", "greeting_message")
    op.drop_column("personas", "description")

    op.drop_table("user_personas")
