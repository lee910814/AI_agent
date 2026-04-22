import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateTurnLog(Base):
    """토론 턴 발언 로그 ORM 모델.

    매치의 각 턴에서 에이전트가 생성한 발언과 LLM 검토 결과를 저장한다.
    패널티·토큰 사용량·응답 시간 등 분석용 메타데이터도 포함한다.

    Attributes:
        id: 턴 로그 고유 UUID.
        match_id: 소속 매치 UUID (debate_matches FK, CASCADE).
        turn_number: 매치 내 순차 턴 번호.
        speaker: 발언 에이전트 구분 (agent_a / agent_b).
        agent_id: 발언 에이전트 UUID (debate_agents FK, CASCADE).
        action: 발언 행동 유형 (argue / rebut / concede / question / summarize).
        claim: 에이전트 주장 본문.
        evidence: 주장 근거 텍스트 (선택).
        tool_used: 사용된 Tool Call 이름 (선택).
        tool_result: Tool Call 실행 결과 텍스트 (선택).
        raw_response: LLM 원시 응답 JSONB.
        penalties: 규칙 위반 패널티 항목 JSONB ({규칙명: 점수}).
        penalty_total: 패널티 합계 점수.
        review_result: LLM 검토 결과 JSONB (논리·허위·주제이탈 점수 등).
        is_blocked: 검토 결과 발언 차단 여부.
        human_suspicion_score: 인간 개입 의심 점수 (0–100).
        response_time_ms: LLM 응답 소요 시간 (밀리초).
        input_tokens: LLM 입력 토큰 수.
        output_tokens: LLM 출력 토큰 수.
        created_at: 턴 로그 생성 시각.
    """

    __tablename__ = "debate_turn_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_matches.id", ondelete="CASCADE"), nullable=False
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(10), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    tool_used: Mapped[str | None] = mapped_column(String(50))
    tool_result: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[dict | None] = mapped_column(JSONB)
    penalties: Mapped[dict | None] = mapped_column(JSONB)
    penalty_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    review_result: Mapped[dict | None] = mapped_column(JSONB)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    human_suspicion_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    match = relationship("DebateMatch", back_populates="turns")
    agent = relationship("DebateAgent", foreign_keys=[agent_id])

    __table_args__ = (
        CheckConstraint(
            "speaker IN ('agent_a', 'agent_b')",
            name="ck_debate_turn_logs_speaker",
        ),
        CheckConstraint(
            "action IN ('argue', 'rebut', 'concede', 'question', 'summarize')",
            name="ck_debate_turn_logs_action",
        ),
    )
