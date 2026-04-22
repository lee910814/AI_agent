import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateTopic(Base):
    """토론 주제 ORM 모델.

    에이전트들이 토론할 주제 정보를 저장한다.
    매칭 큐·매치와 연관되며 모드·최대 턴 수·턴 토큰 제한 등을 제어한다.

    Attributes:
        id: 주제 고유 UUID.
        title: 주제 제목 (최대 200자).
        description: 주제 상세 설명 텍스트.
        mode: 토론 형식 (debate / persuasion / cross_exam).
        status: 주제 상태 (scheduled / open / in_progress / closed).
        max_turns: 매치당 최대 턴 수 (기본 6).
        turn_token_limit: 턴당 최대 토큰 수 (기본 2000).
        scheduled_start_at: 예약 시작 시각 (None이면 즉시 오픈).
        scheduled_end_at: 예약 종료 시각.
        is_admin_topic: 관리자가 등록한 주제 여부.
        tools_enabled: Tool Call 허용 여부.
        created_by: 주제 등록 사용자 UUID (users FK).
        created_at: 생성 시각.
        updated_at: 마지막 수정 시각.
        is_password_protected: 비밀번호 보호 여부.
        password_hash: 비밀번호 해시 (보호 시만 사용).
    """

    __tablename__ = "debate_topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="debate")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False, server_default="6")
    turn_token_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2000")
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_admin_topic: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    tools_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    is_password_protected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    matches = relationship("DebateMatch", back_populates="topic")
    queue_entries = relationship("DebateMatchQueue", back_populates="topic", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "mode IN ('debate', 'persuasion', 'cross_exam')",
            name="ck_debate_topics_mode",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'open', 'in_progress', 'closed')",
            name="ck_debate_topics_status",
        ),
    )
