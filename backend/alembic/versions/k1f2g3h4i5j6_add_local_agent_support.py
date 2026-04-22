"""add_local_agent_support

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-02-23 14:00:00.000000

로컬 에이전트 WebSocket 지원.
- debate_agents.provider CHECK에 'local' 추가
- debate_agents.encrypted_api_key nullable 변경 (local은 API 키 불필요)
- debate_matches.status CHECK에 'waiting_agent', 'forfeit' 추가
"""

from typing import Sequence, Union

from alembic import op

revision: str = "k1f2g3h4i5j6"
down_revision: Union[str, None] = "j0e1f2g3h4i5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # debate_agents.provider CHECK에 'local' 추가
    op.drop_constraint("ck_debate_agents_provider", "debate_agents", type_="check")
    op.create_check_constraint(
        "ck_debate_agents_provider",
        "debate_agents",
        "provider IN ('openai', 'anthropic', 'google', 'runpod', 'local')",
    )

    # encrypted_api_key nullable 변경 (local 에이전트는 API 키 불필요)
    op.alter_column("debate_agents", "encrypted_api_key", nullable=True)

    # debate_matches.status CHECK에 'waiting_agent', 'forfeit' 추가
    op.drop_constraint("ck_debate_matches_status", "debate_matches", type_="check")
    op.create_check_constraint(
        "ck_debate_matches_status",
        "debate_matches",
        "status IN ('pending', 'in_progress', 'completed', 'error', 'waiting_agent', 'forfeit')",
    )


def downgrade() -> None:
    # debate_matches.status CHECK 복원
    op.drop_constraint("ck_debate_matches_status", "debate_matches", type_="check")
    op.create_check_constraint(
        "ck_debate_matches_status",
        "debate_matches",
        "status IN ('pending', 'in_progress', 'completed', 'error')",
    )

    # encrypted_api_key NOT NULL 복원
    op.alter_column("debate_agents", "encrypted_api_key", nullable=False)

    # debate_agents.provider CHECK 복원
    op.drop_constraint("ck_debate_agents_provider", "debate_agents", type_="check")
    op.create_check_constraint(
        "ck_debate_agents_provider",
        "debate_agents",
        "provider IN ('openai', 'anthropic', 'google', 'runpod')",
    )
