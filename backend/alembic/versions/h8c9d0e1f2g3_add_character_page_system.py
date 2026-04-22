"""add_character_page_system

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-02-21 10:00:00.000000

인스타그램 스타일 캐릭터 페이지 시스템 추가.
- pending_posts: 수동 모드 승인 큐
- character_chat_sessions: 캐릭터 간 1:1 대화 세션
- character_chat_messages: 대화 메시지
- world_events: 관리자 세계관 이벤트 (大前提)
- personas에 follower_count, post_count 추가
- persona_lounge_configs에 publishing_mode, per-type 한도, 채팅 설정 추가
- board_posts에 character_chat_session_id 추가
- notifications 타입 확장
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h8c9d0e1f2g3"
down_revision: Union[str, None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- personas: follower_count, post_count ---
    op.add_column("personas", sa.Column("follower_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("personas", sa.Column("post_count", sa.Integer(), nullable=False, server_default="0"))

    # --- persona_lounge_configs: 캐릭터 페이지 설정 ---
    op.add_column(
        "persona_lounge_configs",
        sa.Column("publishing_mode", sa.String(20), nullable=False, server_default="auto"),
    )
    op.add_column(
        "persona_lounge_configs",
        sa.Column("daily_post_limit", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "persona_lounge_configs",
        sa.Column("daily_comment_limit", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "persona_lounge_configs",
        sa.Column("daily_chat_limit", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "persona_lounge_configs",
        sa.Column("posts_today", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "persona_lounge_configs",
        sa.Column("comments_today", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "persona_lounge_configs",
        sa.Column("chats_today", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "persona_lounge_configs",
        sa.Column("auto_comment_reply", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "persona_lounge_configs",
        sa.Column("accept_chat_requests", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "persona_lounge_configs",
        sa.Column("auto_accept_chats", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        "ck_lounge_publishing_mode", "persona_lounge_configs", "publishing_mode IN ('auto', 'manual')"
    )

    # --- pending_posts ---
    op.create_table(
        "pending_posts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("target_post_id", sa.UUID(), nullable=True),
        sa.Column("target_comment_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_post_id"], ["board_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_comment_id"], ["board_comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("content_type IN ('post', 'comment')", name="ck_pending_content_type"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_pending_status"),
    )
    op.create_index("idx_pending_owner_status", "pending_posts", ["owner_user_id", "status", "created_at"])
    op.create_index("idx_pending_persona_status", "pending_posts", ["persona_id", "status"])

    # --- character_chat_sessions ---
    op.create_table(
        "character_chat_sessions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("requester_persona_id", sa.UUID(), nullable=False),
        sa.Column("responder_persona_id", sa.UUID(), nullable=False),
        sa.Column("requester_owner_id", sa.UUID(), nullable=False),
        sa.Column("responder_owner_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("max_turns", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("current_turn", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("age_rating", sa.String(20), nullable=False, server_default="all"),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["requester_persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responder_persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responder_owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'rejected', 'cancelled')",
            name="ck_cc_session_status",
        ),
        sa.CheckConstraint("age_rating IN ('all', '15+', '18+')", name="ck_cc_session_age_rating"),
        sa.CheckConstraint("max_turns BETWEEN 1 AND 20", name="ck_cc_max_turns"),
    )
    op.create_index("idx_cc_requester_status", "character_chat_sessions", ["requester_persona_id", "status"])
    op.create_index("idx_cc_responder_status", "character_chat_sessions", ["responder_persona_id", "status"])
    op.create_index("idx_cc_req_owner_status", "character_chat_sessions", ["requester_owner_id", "status"])
    op.create_index("idx_cc_resp_owner_status", "character_chat_sessions", ["responder_owner_id", "status"])
    # 같은 캐릭터 쌍 간 동시 active 세션 1개
    op.execute("""
        CREATE UNIQUE INDEX uq_cc_active_pair
        ON character_chat_sessions (requester_persona_id, responder_persona_id)
        WHERE status = 'active'
    """)

    # --- character_chat_messages ---
    op.create_table(
        "character_chat_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["character_chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ccm_session_turn", "character_chat_messages", ["session_id", "turn_number"])

    # --- world_events ---
    op.create_table(
        "world_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False, server_default="world_state"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("age_rating", sa.String(20), nullable=False, server_default="all"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "event_type IN ('world_state', 'seasonal', 'crisis', 'lore_update')",
            name="ck_world_event_type",
        ),
        sa.CheckConstraint("age_rating IN ('all', '15+', '18+')", name="ck_world_event_age_rating"),
    )
    op.create_index("idx_world_events_active", "world_events", ["is_active", "priority"])

    # --- board_posts: character_chat_session_id ---
    op.add_column(
        "board_posts",
        sa.Column("character_chat_session_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_posts_cc_session", "board_posts", "character_chat_sessions",
        ["character_chat_session_id"], ["id"], ondelete="SET NULL",
    )

    # --- notifications: 타입 확장 ---
    op.drop_constraint("ck_notification_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_type",
        "notifications",
        "type IN ('persona_approved','persona_blocked','reply','system','relationship','credit',"
        "'follow','chat_request','chat_accepted','pending_post','world_event')",
    )

    # --- backfill: follower_count, post_count ---
    op.execute("""
        UPDATE personas SET follower_count = (
            SELECT COUNT(*) FROM persona_favorites WHERE persona_id = personas.id
        )
    """)
    op.execute("""
        UPDATE personas SET post_count = (
            SELECT COUNT(*) FROM board_posts
            WHERE author_persona_id = personas.id AND is_hidden = false
        )
    """)


def downgrade() -> None:
    # notifications: 타입 복원
    op.drop_constraint("ck_notification_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_type",
        "notifications",
        "type IN ('persona_approved','persona_blocked','reply','system','relationship','credit')",
    )

    # board_posts: character_chat_session_id 제거
    op.drop_constraint("fk_posts_cc_session", "board_posts", type_="foreignkey")
    op.drop_column("board_posts", "character_chat_session_id")

    # world_events
    op.drop_index("idx_world_events_active", table_name="world_events")
    op.drop_table("world_events")

    # character_chat_messages
    op.drop_index("idx_ccm_session_turn", table_name="character_chat_messages")
    op.drop_table("character_chat_messages")

    # character_chat_sessions
    op.execute("DROP INDEX IF EXISTS uq_cc_active_pair")
    op.drop_index("idx_cc_resp_owner_status", table_name="character_chat_sessions")
    op.drop_index("idx_cc_req_owner_status", table_name="character_chat_sessions")
    op.drop_index("idx_cc_responder_status", table_name="character_chat_sessions")
    op.drop_index("idx_cc_requester_status", table_name="character_chat_sessions")
    op.drop_table("character_chat_sessions")

    # pending_posts
    op.drop_index("idx_pending_persona_status", table_name="pending_posts")
    op.drop_index("idx_pending_owner_status", table_name="pending_posts")
    op.drop_table("pending_posts")

    # persona_lounge_configs: 신규 컬럼 제거
    op.drop_constraint("ck_lounge_publishing_mode", "persona_lounge_configs", type_="check")
    op.drop_column("persona_lounge_configs", "auto_accept_chats")
    op.drop_column("persona_lounge_configs", "accept_chat_requests")
    op.drop_column("persona_lounge_configs", "auto_comment_reply")
    op.drop_column("persona_lounge_configs", "chats_today")
    op.drop_column("persona_lounge_configs", "comments_today")
    op.drop_column("persona_lounge_configs", "posts_today")
    op.drop_column("persona_lounge_configs", "daily_chat_limit")
    op.drop_column("persona_lounge_configs", "daily_comment_limit")
    op.drop_column("persona_lounge_configs", "daily_post_limit")
    op.drop_column("persona_lounge_configs", "publishing_mode")

    # personas: 신규 컬럼 제거
    op.drop_column("personas", "post_count")
    op.drop_column("personas", "follower_count")
