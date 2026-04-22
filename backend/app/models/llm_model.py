import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMModel(Base):
    """등록된 LLM 모델 ORM 모델.

    플랫폼에서 사용 가능한 LLM 모델의 설정과 비용 정보를 저장한다.
    ``InferenceClient``가 이 테이블을 조회해 provider 및 비용을 결정한다.

    Attributes:
        id: 모델 고유 UUID.
        provider: LLM 공급사 식별자 (openai / anthropic / google / runpod 등).
        model_id: 공급사 API에서 사용하는 모델 식별자 문자열.
        display_name: 사용자 화면 표시 이름.
        input_cost_per_1m: 입력 토큰 1M당 비용 (USD).
        output_cost_per_1m: 출력 토큰 1M당 비용 (USD).
        max_context_length: 최대 컨텍스트 토큰 수.
        is_adult_only: 성인 전용 모델 여부.
        is_active: 활성 모델 여부 (비활성 시 신규 에이전트 선택 불가).
        tier: 모델 티어 (economy / standard / premium).
        credit_per_1k_tokens: 1,000토큰당 차감 크레딧.
        metadata_: 추가 메타데이터 JSONB (컬럼명 ``metadata``).
        created_at: 모델 등록 시각.
    """

    __tablename__ = "llm_models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_cost_per_1m: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    output_cost_per_1m: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    max_context_length: Mapped[int] = mapped_column(Integer, nullable=False)
    is_adult_only: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="economy")
    credit_per_1k_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("provider", "model_id", name="uq_llm_provider_model"),
        CheckConstraint("tier IN ('economy', 'standard', 'premium')", name="ck_llm_tier"),
    )
