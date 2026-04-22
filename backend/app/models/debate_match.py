import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateMatch(Base):
    """토론 매치 ORM 모델.

    두 에이전트가 특정 주제로 진행하는 단일 매치의 전체 상태를 저장한다.
    점수·패널티·ELO 변동·시즌/시리즈 연결 정보를 통합 관리한다.

    Attributes:
        id: 매치 고유 UUID.
        topic_id: 토론 주제 UUID (debate_topics FK).
        agent_a_id: A 에이전트 UUID (debate_agents FK).
        agent_b_id: B 에이전트 UUID (debate_agents FK).
        agent_a_version_id: 매치 시 사용된 A 에이전트 버전 UUID.
        agent_b_version_id: 매치 시 사용된 B 에이전트 버전 UUID.
        status: 매치 상태 (pending / in_progress / completed / error / waiting_agent / forfeit).
        is_test: 관리자 테스트 매치 여부 (True이면 ELO 미반영).
        winner_id: 승리한 에이전트 UUID (무승부이면 None).
        scorecard: 판정 세부 점수 JSONB ({agent_a: {...}, agent_b: {...}, reasoning: "..."}).
        score_a: A 에이전트 획득 점수.
        score_b: B 에이전트 획득 점수.
        penalty_a: A 에이전트 누적 패널티.
        penalty_b: B 에이전트 누적 패널티.
        started_at: 매치 시작 시각.
        finished_at: 매치 종료 시각.
        elo_a_before: A 에이전트 매치 전 ELO.
        elo_b_before: B 에이전트 매치 전 ELO.
        elo_a_after: A 에이전트 매치 후 ELO.
        elo_b_after: B 에이전트 매치 후 ELO.
        is_featured: 주간 하이라이트 선정 여부.
        featured_at: 하이라이트 선정 시각.
        tournament_id: 소속 토너먼트 UUID (debate_tournaments FK).
        tournament_round: 토너먼트 내 라운드 번호.
        format: 매치 형식 (1v1 / 2v2 등).
        summary_report: 토론 요약 리포트 JSONB.
        season_id: 소속 시즌 UUID (debate_seasons FK).
        match_type: 매치 유형 (ranked / promotion / demotion).
        series_id: 소속 승급전/강등전 시리즈 UUID.
        credits_deducted: 몰수패 처리 시 차감된 크레딧.
        error_reason: 오류 또는 몰수패 사유 메시지.
        created_at: 매치 생성 시각.
    """

    __tablename__ = "debate_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_topics.id", ondelete="CASCADE"), nullable=False
    )
    agent_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    agent_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    agent_a_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agent_versions.id", ondelete="SET NULL")
    )
    agent_b_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agent_versions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    # 관리자 강제 매치(테스트) 여부 — True이면 항상 플랫폼 키 사용, ELO 미반영
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    winner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # 스코어카드: {agent_a: {logic: 28, evidence: 22, ...}, agent_b: {...}, reasoning: "..."}
    scorecard: Mapped[dict | None] = mapped_column(JSONB)
    score_a: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    score_b: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    penalty_a: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    penalty_b: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elo_a_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elo_b_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elo_a_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elo_b_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 기능 7: 주간 하이라이트
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    featured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 기능 9: 토너먼트 연계
    tournament_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_tournaments.id", ondelete="SET NULL"), nullable=True
    )
    tournament_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 기능 10: 멀티 에이전트 포맷
    format: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'1v1'"))
    # 기능 11: 토론 요약 리포트
    summary_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 시즌 매치: 활성 시즌 진행 중일 때 자동 태깅
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debate_seasons.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 승급전/강등전 시스템
    match_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ranked")
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debate_promotion_series.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 몰수패/부전패 처리 시 차감된 크레딧 및 오류 사유
    credits_deducted: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    topic = relationship("DebateTopic", back_populates="matches")
    agent_a = relationship("DebateAgent", foreign_keys=[agent_a_id])
    agent_b = relationship("DebateAgent", foreign_keys=[agent_b_id])
    agent_a_version = relationship("DebateAgentVersion", foreign_keys=[agent_a_version_id])
    agent_b_version = relationship("DebateAgentVersion", foreign_keys=[agent_b_version_id])
    turns = relationship(
        "DebateTurnLog", back_populates="match", cascade="all, delete-orphan",
        order_by="DebateTurnLog.turn_number"
    )
    community_posts = relationship("CommunityPost", back_populates="match")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'error', 'waiting_agent', 'forfeit')",
            name="ck_debate_matches_status",
        ),
        CheckConstraint(
            "match_type IN ('ranked', 'promotion', 'demotion')",
            name="ck_debate_matches_match_type",
        ),
    )


# --- DebateMatchParticipant ---

class DebateMatchParticipant(Base):
    """멀티에이전트 매치 참가자 ORM 모델.

    2v2 이상 포맷에서 각 팀의 에이전트 슬롯 배정을 저장한다.
    1v1 기본 포맷에서는 사용되지 않는다.

    Attributes:
        id: 참가자 레코드 고유 UUID.
        match_id: 소속 매치 UUID (debate_matches FK, CASCADE).
        agent_id: 참가 에이전트 UUID (debate_agents FK, CASCADE).
        version_id: 매치 시 사용된 에이전트 버전 UUID.
        team: 팀 구분 ('A' 또는 'B').
        slot: 팀 내 슬롯 번호 (0-indexed).
    """

    __tablename__ = "debate_match_participants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_matches.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agent_versions.id", ondelete="SET NULL"), nullable=True
    )
    team: Mapped[str] = mapped_column(String(1), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)

    agent = relationship("DebateAgent", foreign_keys=[agent_id])
    version = relationship("DebateAgentVersion", foreign_keys=[version_id])

    __table_args__ = (
        CheckConstraint("team IN ('A', 'B')", name="ck_debate_match_participants_team"),
    )


# --- DebateMatchPrediction ---

class DebateMatchPrediction(Base):
    """사용자 예측투표 ORM 모델.

    매치 시작 전 사용자가 승자를 예측한 투표 데이터를 저장한다.
    매치 완료 후 ``is_correct`` 값이 채워진다.
    사용자당 매치당 1회만 투표 가능 (UniqueConstraint).

    Attributes:
        id: 예측 레코드 고유 UUID.
        match_id: 대상 매치 UUID (debate_matches FK, CASCADE).
        user_id: 투표한 사용자 UUID (users FK, CASCADE).
        prediction: 예측 결과 (a_win / b_win / draw).
        is_correct: 예측 정답 여부 (매치 완료 전은 None).
        created_at: 투표 시각.
    """

    __tablename__ = "debate_match_predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_matches.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    prediction: Mapped[str] = mapped_column(String(10), nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "prediction IN ('a_win', 'b_win', 'draw')",
            name="ck_debate_match_predictions_prediction",
        ),
        UniqueConstraint("match_id", "user_id", name="uq_debate_match_predictions_user"),
    )


# --- DebateMatchQueue ---

class DebateMatchQueue(Base):
    """매칭 대기 큐 ORM 모델.

    에이전트가 특정 토픽의 매칭을 기다리는 큐 항목을 저장한다.
    ``DebateAutoMatcher``가 주기적으로 이 테이블을 스캔해 상대를 찾는다.

    Attributes:
        id: 큐 항목 고유 UUID.
        topic_id: 대기 중인 토픽 UUID (debate_topics FK, CASCADE).
        agent_id: 대기 에이전트 UUID (debate_agents FK, CASCADE).
        user_id: 에이전트 소유자 UUID (users FK, CASCADE).
        joined_at: 큐 등록 시각.
        expires_at: 큐 만료 시각 (만료 시 자동 제거 대상).
        is_ready: 매칭 준비 완료 여부.
    """

    __tablename__ = "debate_match_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_topics.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_ready: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # Relationships
    topic = relationship("DebateTopic", back_populates="queue_entries")
    agent = relationship("DebateAgent", foreign_keys=[agent_id])
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("topic_id", "agent_id", name="uq_debate_queue_topic_agent"),
        Index("idx_debate_queue_user_id", "user_id"),
        Index("idx_debate_queue_agent_id", "agent_id"),
    )
