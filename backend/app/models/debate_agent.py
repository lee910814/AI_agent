import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateAgent(Base):
    """AI 토론 에이전트 ORM 모델.

    사용자가 생성한 AI 에이전트의 설정과 누적 전적을 저장한다.
    ELO 점수·티어·승급전 상태·플랫폼 크레딧 사용 여부 등을 관리한다.

    Attributes:
        id: 에이전트 고유 UUID.
        owner_id: 소유자 사용자 UUID (users FK).
        name: 에이전트 이름 (최대 100자).
        description: 에이전트 설명 텍스트.
        provider: LLM 공급사 (openai / anthropic / google / runpod / local).
        model_id: 공급사별 모델 식별자 문자열.
        encrypted_api_key: Fernet 암호화된 API 키 (local 에이전트는 None).
        image_url: 프로필 이미지 URL.
        template_id: 기반 템플릿 UUID (debate_agent_templates FK).
        customizations: 템플릿 커스터마이징 값 (flat JSONB dict).
        elo_rating: 누적 ELO 점수 (기본 1500).
        wins: 누적 승리 수.
        losses: 누적 패배 수.
        draws: 누적 무승부 수.
        is_active: 활성 에이전트 여부.
        is_platform: 플랫폼 공식 에이전트 여부.
        name_changed_at: 마지막 이름 변경 시각 (7일 1회 제한).
        is_system_prompt_public: 시스템 프롬프트 공개 여부.
        use_platform_credits: 플랫폼 크레딧으로 API 비용 지불 여부.
        tier: 현재 티어 (Iron / Bronze / Silver / Gold 등).
        tier_protection_count: 티어 강등 보호 횟수.
        active_series_id: 진행 중인 승급전/강등전 시리즈 UUID.
        is_profile_public: 프로필 공개 여부.
        created_at: 에이전트 생성 시각.
        updated_at: 마지막 수정 시각.
    """

    __tablename__ = "debate_agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # Fernet 암호화된 API 키 (local 에이전트는 API 키 불필요)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 템플릿 기반 에이전트: 선택한 템플릿 ID
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debate_agent_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 템플릿 커스터마이징 값 (flat dict: {"aggression": 4, "tone": "formal", ...})
    customizations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    elo_rating: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1500")
    wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draws: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    is_platform: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    # 이름 변경 제한 (7일 1회)
    name_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 시스템 프롬프트 공개 여부 (소유자 결정)
    is_system_prompt_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # 플랫폼 크레딧으로 API 비용 지불 (BYOK API 키 불필요)
    use_platform_credits: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="Iron")
    tier_protection_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 활성 승급전/강등전 시리즈 (매칭 시 빠른 조회용)
    active_series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debate_promotion_series.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_profile_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    template = relationship("DebateAgentTemplate", foreign_keys=[template_id])
    versions = relationship(
        "DebateAgentVersion", back_populates="agent", cascade="all, delete-orphan",
        order_by="DebateAgentVersion.version_number.desc()"
    )
    community_posts = relationship("CommunityPost", back_populates="agent")

    __table_args__ = (
        CheckConstraint(
            "provider IN ('openai', 'anthropic', 'google', 'runpod', 'local')",
            name="ck_debate_agents_provider",
        ),
    )


# --- DebateAgentVersion ---

class DebateAgentVersion(Base):
    """에이전트 버전 이력 ORM 모델.

    에이전트의 시스템 프롬프트 변경 이력을 스냅샷으로 저장한다.
    매치 시 사용된 정확한 프롬프트 버전을 추적하는 데 쓰인다.

    Attributes:
        id: 버전 고유 UUID.
        agent_id: 소속 에이전트 UUID (debate_agents FK, CASCADE).
        version_number: 순차 버전 번호.
        version_tag: 사람이 읽기 쉬운 버전 태그 (예: "v2-공격형").
        system_prompt: 해당 버전의 시스템 프롬프트 전문.
        parameters: 추가 파라미터 JSONB (temperature 등).
        wins: 이 버전으로 획득한 승리 수.
        losses: 이 버전으로 기록된 패배 수.
        draws: 이 버전으로 기록된 무승부 수.
        created_at: 버전 생성 시각.
    """

    __tablename__ = "debate_agent_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_tag: Mapped[str | None] = mapped_column(String(50))
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draws: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    agent = relationship("DebateAgent", back_populates="versions")


# --- DebateAgentSeasonStats ---

class DebateAgentSeasonStats(Base):
    """에이전트 시즌별 전적 통계 ORM 모델.

    시즌마다 ELO·티어·전적을 독립적으로 집계한다.
    시즌 시작 시 ELO는 1500으로 초기화되며 누적 전적과 분리된다.

    Attributes:
        id: 통계 레코드 고유 UUID.
        agent_id: 에이전트 UUID (debate_agents FK, CASCADE).
        season_id: 시즌 UUID (debate_seasons FK, CASCADE).
        elo_rating: 시즌 ELO 점수 (기본 1500).
        tier: 시즌 내 티어.
        wins: 시즌 승리 수.
        losses: 시즌 패배 수.
        draws: 시즌 무승부 수.
        created_at: 레코드 생성 시각.
        updated_at: 마지막 갱신 시각.
    """

    __tablename__ = "debate_agent_season_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_seasons.id", ondelete="CASCADE"), nullable=False
    )
    # 시즌 ELO: 매 시즌 1500으로 초기화
    elo_rating: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1500")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="Iron")
    wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draws: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()")
    )

    agent = relationship("DebateAgent")
    season = relationship("DebateSeason")

    __table_args__ = (
        # 에이전트당 시즌당 1행
        UniqueConstraint("agent_id", "season_id", name="uq_season_stats_agent_season"),
    )
