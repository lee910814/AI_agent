"""debate_agent_name_limit_prompt_public_credit_debate

Revision ID: r8m9n0o1p2q3
Revises: q7l8m9n0o1p6
Create Date: 2026-02-25 13:00:00.000000

3개 변경사항 통합:
1. debate_agents — name_changed_at (DateTime, nullable) 추가: 이름 변경 7일 제한 추적
2. debate_agents — is_system_prompt_public (Boolean, default=false) 추가: 소유자 결정 프롬프트 공개
3. credit_ledger — tx_type CHECK 제약조건에 'debate' 추가: 토론 매치 크레딧 차감 지원
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r8m9n0o1p2q3"
down_revision: Union[str, None] = "q7l8m9n0o1p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. debate_agents — name_changed_at 추가
    op.add_column(
        "debate_agents",
        sa.Column("name_changed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. debate_agents — is_system_prompt_public 추가
    op.add_column(
        "debate_agents",
        sa.Column(
            "is_system_prompt_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 3. credit_ledger — tx_type CHECK 제약조건 갱신 ('debate' 추가)
    op.drop_constraint("ck_ledger_tx_type", "credit_ledger", type_="check")
    op.create_check_constraint(
        "ck_ledger_tx_type",
        "credit_ledger",
        "tx_type IN ("
        "'daily_grant','purchase','chat','lounge_post','lounge_comment',"
        "'review','agent_action','expire','admin_grant','refund','debate'"
        ")",
    )


def downgrade() -> None:
    # credit_ledger CHECK 원복
    op.drop_constraint("ck_ledger_tx_type", "credit_ledger", type_="check")
    op.create_check_constraint(
        "ck_ledger_tx_type",
        "credit_ledger",
        "tx_type IN ("
        "'daily_grant','purchase','chat','lounge_post','lounge_comment',"
        "'review','agent_action','expire','admin_grant','refund'"
        ")",
    )

    op.drop_column("debate_agents", "is_system_prompt_public")
    op.drop_column("debate_agents", "name_changed_at")
