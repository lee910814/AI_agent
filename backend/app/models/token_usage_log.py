import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TokenUsageLog(Base):
    """LLM 토큰 사용량 로그 ORM 모델.

    모든 LLM 호출의 토큰 수와 비용을 기록한다.
    사용자별·모델별 집계로 과금 근거 및 사용량 현황을 제공한다.

    Attributes:
        id: 로그 레코드 자동 증가 BigInteger PK.
        user_id: 호출한 사용자 UUID (users FK, CASCADE).
        session_id: 관련 세션 UUID (선택, FK 없음).
        match_id: 토론 매치 UUID (debate_matches FK, 선택). 토론 엔진 호출에만 기록.
        llm_model_id: 사용한 LLM 모델 UUID (llm_models FK).
        input_tokens: 입력 토큰 수.
        output_tokens: 출력 토큰 수.
        cost: 호출 비용 (USD, 소수점 6자리).
        created_at: 호출 시각.
    """

    __tablename__ = "token_usage_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # chat_sessions FK 제거 — 토론 플랫폼에는 해당 테이블이 없어 SQLAlchemy 매퍼 오류 발생
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debate_matches.id", ondelete="SET NULL"),
        nullable=True,
    )
    llm_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_models.id"), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    user = relationship("User")
    llm_model = relationship("LLMModel")
    match = relationship("DebateMatch", foreign_keys=[match_id])

    __table_args__ = (
        Index("idx_usage_user", "user_id", "created_at"),
        Index("idx_usage_model", "llm_model_id", "created_at"),
        Index("idx_usage_session", "session_id"),
        Index("idx_usage_match", "match_id"),
    )
