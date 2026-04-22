"""add_debate_platform

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-02-23 10:00:00.000000

AI 토론 플랫폼 테이블 추가.
- debate_agents: 에이전트 정보 (BYOK API 키, ELO, 전적)
- debate_agent_versions: 프롬프트 버전 이력
- debate_topics: 토론 주제
- debate_matches: 매치 기록 + 스코어카드
- debate_turn_logs: 턴별 로그
- debate_match_queue: 매칭 큐
- users.role CHECK 유지 (user/admin/superadmin)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "j0e1f2g3h4i5"
down_revision: Union[str, None] = "i9d0e1f2g3h4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- debate_agents ---
    op.create_table(
        "debate_agents",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("elo_rating", sa.Integer(), nullable=False, server_default="1500"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "provider IN ('openai', 'anthropic', 'google', 'runpod')",
            name="ck_debate_agents_provider",
        ),
    )
    op.create_index("idx_debate_agents_owner", "debate_agents", ["owner_id"])
    op.create_index("idx_debate_agents_elo", "debate_agents", ["elo_rating"], postgresql_using="btree")

    # --- debate_agent_versions ---
    op.create_table(
        "debate_agent_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_tag", sa.String(50), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["debate_agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "version_number", name="uq_agent_version"),
    )
    op.create_index("idx_debate_versions_agent", "debate_agent_versions", ["agent_id", "version_number"])

    # --- debate_topics ---
    op.create_table(
        "debate_topics",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mode", sa.String(20), nullable=False, server_default="debate"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("max_turns", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("turn_token_limit", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("mode IN ('debate', 'persuasion', 'cross_exam')", name="ck_debate_topics_mode"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'closed')", name="ck_debate_topics_status"),
    )
    op.create_index("idx_debate_topics_status", "debate_topics", ["status", "created_at"])

    # --- debate_matches ---
    op.create_table(
        "debate_matches",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.Column("agent_a_id", sa.UUID(), nullable=False),
        sa.Column("agent_b_id", sa.UUID(), nullable=False),
        sa.Column("agent_a_version_id", sa.UUID(), nullable=True),
        sa.Column("agent_b_version_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("winner_id", sa.UUID(), nullable=True),
        sa.Column("scorecard", sa.JSON(), nullable=True),
        sa.Column("score_a", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_b", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("penalty_a", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("penalty_b", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["debate_topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_a_id"], ["debate_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_b_id"], ["debate_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_a_version_id"], ["debate_agent_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_b_version_id"], ["debate_agent_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'error')",
            name="ck_debate_matches_status",
        ),
    )
    op.create_index("idx_debate_matches_topic", "debate_matches", ["topic_id", "status"])
    op.create_index("idx_debate_matches_agent_a", "debate_matches", ["agent_a_id"])
    op.create_index("idx_debate_matches_agent_b", "debate_matches", ["agent_b_id"])

    # --- debate_turn_logs ---
    op.create_table(
        "debate_turn_logs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("match_id", sa.UUID(), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(10), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("tool_used", sa.String(50), nullable=True),
        sa.Column("tool_result", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("penalties", sa.JSON(), nullable=True),
        sa.Column("penalty_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["debate_matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["debate_agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("speaker IN ('agent_a', 'agent_b')", name="ck_debate_turn_logs_speaker"),
        sa.CheckConstraint(
            "action IN ('argue', 'rebut', 'concede', 'question', 'summarize')",
            name="ck_debate_turn_logs_action",
        ),
    )
    op.create_index("idx_debate_turns_match", "debate_turn_logs", ["match_id", "turn_number"])

    # --- debate_match_queue ---
    op.create_table(
        "debate_match_queue",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["debate_topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["debate_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_id", "agent_id", name="uq_debate_queue_topic_agent"),
    )
    op.create_index("idx_debate_queue_topic", "debate_match_queue", ["topic_id", "joined_at"])


def downgrade() -> None:
    # debate_match_queue
    op.drop_index("idx_debate_queue_topic", table_name="debate_match_queue")
    op.drop_table("debate_match_queue")

    # debate_turn_logs
    op.drop_index("idx_debate_turns_match", table_name="debate_turn_logs")
    op.drop_table("debate_turn_logs")

    # debate_matches
    op.drop_index("idx_debate_matches_agent_b", table_name="debate_matches")
    op.drop_index("idx_debate_matches_agent_a", table_name="debate_matches")
    op.drop_index("idx_debate_matches_topic", table_name="debate_matches")
    op.drop_table("debate_matches")

    # debate_topics
    op.drop_index("idx_debate_topics_status", table_name="debate_topics")
    op.drop_table("debate_topics")

    # debate_agent_versions
    op.drop_index("idx_debate_versions_agent", table_name="debate_agent_versions")
    op.drop_table("debate_agent_versions")

    # debate_agents
    op.drop_index("idx_debate_agents_elo", table_name="debate_agents")
    op.drop_index("idx_debate_agents_owner", table_name="debate_agents")
    op.drop_table("debate_agents")

    # users.role CHECK 복원
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin', 'superadmin')")
