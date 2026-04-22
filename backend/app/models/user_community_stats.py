"""사용자 커뮤니티 참여 통계 모델."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserCommunityStats(Base):
    """사용자별 커뮤니티 활동량 집계 테이블.

    좋아요 횟수 + 팔로우 수를 합산해 tier(Bronze~Diamond)를 산정한다.
    활동 발생 시 비동기 업데이트.
    """

    __tablename__ = "user_community_stats"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_community_stats_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="Bronze")
    likes_given: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    follows_given: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
