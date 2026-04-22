import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DebateAgentTemplate(Base):
    """에이전트 템플릿 ORM 모델.

    관리자가 제공하는 미리 정의된 에이전트 기반 설정을 저장한다.
    사용자는 템플릿을 선택한 뒤 커스터마이징 값만 입력해 에이전트를 생성할 수 있다.

    Attributes:
        id: 템플릿 고유 UUID.
        slug: URL 친화적 식별자 (유니크, 예: "logical-debater").
        display_name: 화면 표시 이름 (최대 100자).
        description: 템플릿 설명 텍스트.
        icon: 아이콘 식별자 문자열 (최대 50자).
        base_system_prompt: 코어 시스템 프롬프트 (``{customization_block}`` 플레이스홀더 포함).
        customization_schema: 커스터마이징 항목 정의 JSONB (sliders, selects, free_text).
        default_values: 커스터마이징 기본값 JSONB flat dict.
        sort_order: 목록 표시 순서.
        is_active: 활성 여부 (비활성 시 신규 생성 불가).
        created_at: 생성 시각.
        updated_at: 마지막 수정 시각.
    """

    __tablename__ = "debate_agent_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 관리자만 편집 가능한 코어 프롬프트. {customization_block} 플레이스홀더 포함.
    base_system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # 커스터마이징 가능 항목 정의 (sliders, selects, free_text)
    customization_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # 기본값 (flat dict: {"aggression": 3, "tone": "neutral", ...})
    default_values: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
