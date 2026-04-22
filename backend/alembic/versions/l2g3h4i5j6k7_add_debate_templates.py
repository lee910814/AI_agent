"""add_debate_templates

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-02-23 16:00:00.000000

토론 에이전트 템플릿 시스템 추가.
- debate_agent_templates: 관리자 제공 템플릿 (slug, base_system_prompt, customization_schema)
- debate_agents: template_id, customizations 컬럼 추가
- 3개 초기 템플릿 시드: 논리형 분석가, 공격형 논객, 균형형 전략가
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l2g3h4i5j6k7"
down_revision: Union[str, None] = "k1f2g3h4i5j6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 공통 커스터마이징 스키마 (3개 템플릿 공유)
_CUSTOMIZATION_SCHEMA = {
    "sliders": [
        {
            "key": "aggression",
            "label": "공격성",
            "min": 1,
            "max": 5,
            "default": 3,
            "description": "높을수록 상대 주장을 적극적으로 반박",
        },
        {
            "key": "evidence_focus",
            "label": "증거 활용도",
            "min": 1,
            "max": 5,
            "default": 3,
            "description": "높을수록 데이터/인용구 활용 증가",
        },
    ],
    "selects": [
        {
            "key": "tone",
            "label": "말투",
            "options": [
                {"value": "formal", "label": "격식체"},
                {"value": "neutral", "label": "중립"},
                {"value": "assertive", "label": "단호함"},
            ],
            "default": "neutral",
        },
        {
            "key": "focus_area",
            "label": "전문 분야",
            "options": [
                {"value": "general", "label": "일반"},
                {"value": "tech", "label": "기술"},
                {"value": "economics", "label": "경제"},
                {"value": "social", "label": "사회"},
            ],
            "default": "general",
        },
    ],
    "free_text": {
        "key": "additional_instructions",
        "label": "추가 지시사항",
        "placeholder": "예: 항상 한국 사례를 인용하세요",
        "max_length": 500,
    },
}

_TEMPLATES = [
    {
        "slug": "logical_analyst",
        "display_name": "논리형 분석가",
        "description": "논리적 근거와 데이터 중심으로 토론합니다. 감정보다 사실로 설득하는 정석 스타일.",
        "icon": "brain",
        "base_system_prompt": (
            "당신은 논리적이고 데이터 중심의 토론 에이전트입니다.\n"
            "모든 주장은 명확한 근거와 논리적 구조에 기반해야 합니다.\n"
            "감정적 호소 대신 사실과 데이터로 설득하세요.\n\n"
            "{customization_block}\n\n"
            "토론 규칙:\n"
            "- 각 주장마다 구체적인 근거를 제시하세요\n"
            "- 상대방의 논리적 오류를 명확히 지적하세요\n"
            "- 허위 주장이나 확인되지 않은 사실은 사용하지 마세요"
        ),
        "customization_schema": _CUSTOMIZATION_SCHEMA,
        "default_values": {
            "aggression": 2,
            "evidence_focus": 4,
            "tone": "formal",
            "focus_area": "general",
        },
        "sort_order": 1,
    },
    {
        "slug": "aggressive_debater",
        "display_name": "공격형 논객",
        "description": "상대방의 약점을 파고드는 공격적 스타일. 주도권을 잡고 수세로 몰아갑니다.",
        "icon": "fire",
        "base_system_prompt": (
            "당신은 공격적이고 적극적인 토론 에이전트입니다.\n"
            "상대방의 약점을 신속히 파악하고 직접적으로 반박하세요.\n"
            "주도권을 잡고 상대방을 수세로 몰아가세요.\n\n"
            "{customization_block}\n\n"
            "토론 규칙:\n"
            "- 상대방의 주장에서 모순과 약점을 즉시 공격하세요\n"
            "- 강력하고 단호한 언어를 사용하세요\n"
            "- 허위 주장이나 확인되지 않은 사실은 사용하지 마세요"
        ),
        "customization_schema": _CUSTOMIZATION_SCHEMA,
        "default_values": {
            "aggression": 5,
            "evidence_focus": 2,
            "tone": "assertive",
            "focus_area": "general",
        },
        "sort_order": 2,
    },
    {
        "slug": "balanced_strategist",
        "display_name": "균형형 전략가",
        "description": "공격과 방어를 균형 있게 조화시킵니다. 상황에 맞는 전술로 장기전에 강합니다.",
        "icon": "scale",
        "base_system_prompt": (
            "당신은 균형 잡힌 전략적 토론 에이전트입니다.\n"
            "공격과 방어를 적절히 조화시키며, 상황에 맞는 전술을 선택하세요.\n"
            "장기적 관점에서 토론 흐름을 관리하세요.\n\n"
            "{customization_block}\n\n"
            "토론 규칙:\n"
            "- 공격과 방어를 상황에 맞게 전환하세요\n"
            "- 상대방의 강점을 인정하되 약점을 전략적으로 활용하세요\n"
            "- 허위 주장이나 확인되지 않은 사실은 사용하지 마세요"
        ),
        "customization_schema": _CUSTOMIZATION_SCHEMA,
        "default_values": {
            "aggression": 3,
            "evidence_focus": 3,
            "tone": "neutral",
            "focus_area": "general",
        },
        "sort_order": 3,
    },
]


def upgrade() -> None:
    # --- debate_agent_templates 테이블 생성 ---
    op.create_table(
        "debate_agent_templates",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("base_system_prompt", sa.Text(), nullable=False),
        sa.Column(
            "customization_schema",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "default_values",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_debate_agent_templates_slug"),
    )
    op.create_index(
        "idx_debate_templates_active",
        "debate_agent_templates",
        ["is_active", "sort_order"],
    )

    # --- debate_agents 컬럼 추가 ---
    op.add_column(
        "debate_agents",
        sa.Column("template_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "debate_agents",
        sa.Column(
            "customizations",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_debate_agents_template_id",
        "debate_agents",
        "debate_agent_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_debate_agents_template", "debate_agents", ["template_id"]
    )

    # --- 초기 템플릿 시드 데이터 ---
    conn = op.get_bind()
    for tmpl in _TEMPLATES:
        conn.execute(
            sa.text(
                """
                INSERT INTO debate_agent_templates
                    (slug, display_name, description, icon, base_system_prompt,
                     customization_schema, default_values, sort_order, is_active)
                VALUES
                    (:slug, :display_name, :description, :icon, :base_system_prompt,
                     CAST(:customization_schema AS jsonb), CAST(:default_values AS jsonb),
                     :sort_order, true)
                ON CONFLICT (slug) DO NOTHING
                """
            ),
            {
                "slug": tmpl["slug"],
                "display_name": tmpl["display_name"],
                "description": tmpl["description"],
                "icon": tmpl["icon"],
                "base_system_prompt": tmpl["base_system_prompt"],
                "customization_schema": json.dumps(
                    tmpl["customization_schema"], ensure_ascii=False
                ),
                "default_values": json.dumps(
                    tmpl["default_values"], ensure_ascii=False
                ),
                "sort_order": tmpl["sort_order"],
            },
        )


def downgrade() -> None:
    op.drop_index("idx_debate_agents_template", table_name="debate_agents")
    op.drop_constraint(
        "fk_debate_agents_template_id", "debate_agents", type_="foreignkey"
    )
    op.drop_column("debate_agents", "customizations")
    op.drop_column("debate_agents", "template_id")

    op.drop_index("idx_debate_templates_active", table_name="debate_agent_templates")
    op.drop_table("debate_agent_templates")
