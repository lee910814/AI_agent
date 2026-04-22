import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """사용자 계정 ORM 모델.

    플랫폼 사용자의 인증 정보, 역할, 크레딧 잔액을 저장한다.
    역할은 user / admin / superadmin 세 단계로 구분된다.

    Attributes:
        id: 사용자 고유 UUID.
        login_id: 로그인 아이디 (최대 30자, 유니크).
        nickname: 표시 이름 (최대 50자, 유니크).
        email_hash: 이메일 SHA-256 해시 (원본 미저장).
        password_hash: 비밀번호 해시 (소셜 로그인 시 None).
        role: 권한 역할 (user / admin / superadmin).
        age_group: 연령 인증 상태 (minor_safe / adult_verified / unverified).
        adult_verified_at: 성인 인증 완료 시각.
        auth_method: 인증 방식 (local / google / kakao 등).
        preferred_llm_model_id: 선호 LLM 모델 FK.
        preferred_themes: 관심 테마 태그 배열.
        credit_balance: 보유 플랫폼 크레딧.
        daily_token_limit: 일일 토큰 사용 한도 (None이면 무제한).
        monthly_token_limit: 월간 토큰 사용 한도 (None이면 무제한).
        last_credit_grant_at: 마지막 크레딧 지급 시각.
        banned_until: 제재 만료 시각 (None이면 정상 계정).
        created_at: 계정 생성 시각.
        updated_at: 마지막 수정 시각.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    login_id: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email_hash: Mapped[str | None] = mapped_column(String(64))
    password_hash: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    age_group: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unverified")
    adult_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_method: Mapped[str | None] = mapped_column(String(20))
    preferred_llm_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_models.id"))
    preferred_themes: Mapped[list[str] | None] = mapped_column(ARRAY(String(30)), nullable=True)
    credit_balance: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    daily_token_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_token_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_credit_grant_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationships - only keep relationships to models that exist
    preferred_llm_model = relationship("LLMModel", foreign_keys=[preferred_llm_model_id])
    community_post_likes = relationship("CommunityPostLike", back_populates="user")
    community_post_dislikes = relationship("CommunityPostDislike", back_populates="user")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin', 'superadmin')", name="ck_users_role"),
        CheckConstraint("age_group IN ('minor_safe', 'adult_verified', 'unverified')", name="ck_users_age_group"),
    )
