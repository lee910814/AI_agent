import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateSeason(Base):
    """토론 시즌 ORM 모델.

    정해진 기간 동안 진행되는 ELO 랭킹 시즌의 기본 정보를 저장한다.
    시즌 기간 중 발생한 매치는 ``season_id``로 태깅되어 별도 집계된다.

    Attributes:
        id: 시즌 고유 UUID.
        season_number: 순차 시즌 번호 (유니크).
        title: 시즌 제목 (예: "Season 1").
        start_at: 시즌 시작 시각.
        end_at: 시즌 종료 시각.
        status: 시즌 상태 (upcoming / active / completed).
        created_at: 시즌 생성 시각.
    """

    __tablename__ = "debate_seasons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    season_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="upcoming")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    results = relationship("DebateSeasonResult", back_populates="season", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('upcoming', 'active', 'completed')",
            name="ck_debate_seasons_status",
        ),
    )


# --- DebateSeasonResult ---

class DebateSeasonResult(Base):
    """시즌 종료 결과 스냅샷 ORM 모델.

    시즌 종료 시 각 에이전트의 최종 순위·ELO·티어를 스냅샷으로 저장한다.
    시즌이 삭제되더라도 순위 기록 보존이 필요한 경우를 대비한 아카이브 역할도 한다.

    Attributes:
        id: 결과 레코드 고유 UUID.
        season_id: 소속 시즌 UUID (debate_seasons FK, CASCADE).
        agent_id: 에이전트 UUID (debate_agents FK, CASCADE).
        final_elo: 시즌 종료 ELO 점수.
        final_tier: 시즌 종료 티어.
        wins: 시즌 내 총 승리 수.
        losses: 시즌 내 총 패배 수.
        draws: 시즌 내 총 무승부 수.
        rank: 시즌 최종 순위.
        reward_credits: 순위 보상으로 지급된 크레딧.
        created_at: 결과 기록 시각.
    """

    __tablename__ = "debate_season_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_seasons.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    final_elo: Mapped[int] = mapped_column(Integer, nullable=False)
    final_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draws: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_credits: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    season = relationship("DebateSeason", back_populates="results")
    agent = relationship("DebateAgent", foreign_keys=[agent_id])
