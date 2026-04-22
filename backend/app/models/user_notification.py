import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserNotification(Base):
    """사용자 알림 ORM 모델.

    매치 이벤트·예측 결과·신규 팔로워 등 플랫폼 알림을 저장한다.
    미읽기 알림 목록 조회 성능을 위해 복합 인덱스를 사용한다.

    Attributes:
        id: 알림 고유 UUID.
        user_id: 알림 수신 사용자 UUID (users FK, CASCADE).
        type: 알림 유형 문자열 (예: match_completed, prediction_result, new_follower).
        title: 알림 제목 (최대 200자).
        body: 알림 본문 텍스트 (선택, 최대 500자).
        link: 관련 페이지 URL (선택, 최대 300자).
        is_read: 읽음 여부 (기본 False).
        created_at: 알림 생성 시각.
    """

    __tablename__ = "user_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 알림 유형: 매치 이벤트, 예측 결과, 신규 팔로워
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        # 미읽기 알림 목록 조회: user_id + is_read 필터 후 최신순 정렬
        Index("idx_user_notifications_user_unread", "user_id", "is_read", "created_at"),
    )
