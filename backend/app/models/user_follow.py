import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserFollow(Base):
    """사용자 팔로우 관계 ORM 모델.

    사용자가 다른 사용자 또는 에이전트를 팔로우하는 관계를 저장한다.
    타겟이 user와 agent 두 종류이므로 다형성 타겟 패턴을 사용한다
    (FK 없이 target_type + target_id UUID 조합으로 식별).

    Attributes:
        id: 팔로우 레코드 고유 UUID.
        follower_id: 팔로우한 사용자 UUID (users FK, CASCADE).
        target_type: 팔로우 대상 유형 ('user' 또는 'agent').
        target_id: 팔로우 대상 UUID (FK 없음, 이종 타겟 지원).
        created_at: 팔로우 시각.
    """

    __tablename__ = "user_follows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    follower_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 다형성 타겟: 'user' 또는 'agent'. FK 없이 UUID만 저장 (이종 타겟 지원)
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    follower = relationship("User", foreign_keys=[follower_id])

    __table_args__ = (
        CheckConstraint("target_type IN ('user', 'agent')", name="ck_user_follows_target_type"),
        UniqueConstraint("follower_id", "target_type", "target_id", name="uq_user_follows_follower_target"),
        # 팔로워 수 카운트용: target_type, target_id 기준 집계
        Index("idx_user_follows_target", "target_type", "target_id"),
        # 내 팔로우 목록 조회용
        Index("idx_user_follows_follower", "follower_id"),
    )
