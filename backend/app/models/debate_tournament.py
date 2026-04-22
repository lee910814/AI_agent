import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateTournament(Base):
    """토너먼트 ORM 모델.

    에이전트들이 참가하는 싱글 엘리미네이션 토너먼트 정보를 저장한다.
    대진 크기는 4 / 8 / 16 중 하나로 고정되며, 라운드별로 매치가 자동 생성된다.

    Attributes:
        id: 토너먼트 고유 UUID.
        title: 토너먼트 제목 (최대 200자).
        topic_id: 사용할 토론 주제 UUID (debate_topics FK, CASCADE).
        status: 토너먼트 상태 (registration / in_progress / completed / cancelled).
        bracket_size: 대진표 크기 (4 / 8 / 16).
        current_round: 현재 진행 라운드 번호 (0은 미시작).
        created_by: 토너먼트 생성 사용자 UUID (users FK).
        winner_agent_id: 우승 에이전트 UUID (완료 전은 None).
        started_at: 토너먼트 시작 시각.
        finished_at: 토너먼트 종료 시각.
        created_at: 토너먼트 생성 시각.
    """

    __tablename__ = "debate_tournaments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_topics.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="registration")
    bracket_size: Mapped[int] = mapped_column(Integer, nullable=False)
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    winner_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    topic = relationship("DebateTopic", foreign_keys=[topic_id])
    creator = relationship("User", foreign_keys=[created_by])
    winner_agent = relationship("DebateAgent", foreign_keys=[winner_agent_id])
    entries = relationship("DebateTournamentEntry", back_populates="tournament", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('registration', 'in_progress', 'completed', 'cancelled')",
            name="ck_debate_tournaments_status",
        ),
        CheckConstraint(
            "bracket_size IN (4, 8, 16)",
            name="ck_debate_tournaments_bracket_size",
        ),
    )


# --- DebateTournamentEntry ---

class DebateTournamentEntry(Base):
    """토너먼트 참가 에이전트 ORM 모델.

    토너먼트에 등록된 각 에이전트의 시드 배정과 탈락 여부를 저장한다.

    Attributes:
        id: 참가 레코드 고유 UUID.
        tournament_id: 소속 토너먼트 UUID (debate_tournaments FK, CASCADE).
        agent_id: 참가 에이전트 UUID (debate_agents FK, CASCADE).
        seed: 대진표 시드 번호 (낮을수록 상위 시드).
        eliminated_at: 탈락 시각 (진행 중이면 None).
        eliminated_round: 탈락 라운드 번호 (진행 중이면 None).
    """

    __tablename__ = "debate_tournament_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_tournaments.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    eliminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eliminated_round: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tournament = relationship("DebateTournament", back_populates="entries")
    agent = relationship("DebateAgent", foreign_keys=[agent_id])
