import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebatePromotionSeries(Base):
    """승급전/강등전 시리즈 ORM 모델.

    에이전트의 티어 변동을 결정하는 다전제 시리즈 진행 상태를 저장한다.
    승급전은 3판 2선승, 강등전은 1판 필승 방식으로 운영된다.

    Attributes:
        id: 시리즈 고유 UUID.
        agent_id: 대상 에이전트 UUID (debate_agents FK, CASCADE).
        series_type: 시리즈 유형 (promotion / demotion).
        from_tier: 시리즈 시작 전 티어.
        to_tier: 성공 시 이동할 티어.
        required_wins: 시리즈 통과에 필요한 최소 승리 수.
        current_wins: 현재까지 획득한 승리 수.
        current_losses: 현재까지 기록된 패배 수.
        draw_count: 현재까지 기록된 무승부 수.
        status: 시리즈 상태 (active / won / lost / cancelled / expired).
        created_at: 시리즈 생성 시각.
        completed_at: 시리즈 종료 시각 (진행 중이면 None).
    """

    __tablename__ = "debate_promotion_series"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    series_type: Mapped[str] = mapped_column(String(20), nullable=False)
    from_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    to_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    required_wins: Mapped[int] = mapped_column(Integer, nullable=False)
    current_wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    current_losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draw_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("DebateAgent", foreign_keys=[agent_id])

    __table_args__ = (
        CheckConstraint(
            "series_type IN ('promotion', 'demotion')",
            name="ck_promotion_series_type",
        ),
        CheckConstraint(
            "status IN ('active', 'won', 'lost', 'cancelled', 'expired')",
            name="ck_promotion_series_status",
        ),
    )
