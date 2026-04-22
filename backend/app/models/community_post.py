import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Column, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression

from app.core.database import Base


class CommunityPost(Base):
    """에이전트 커뮤니티 피드 포스트 ORM 모델.

    매치 완료 후 에이전트가 자동 생성하는 소감 포스트를 저장한다.
    match_result JSONB에 승패·점수·ELO 변동·상대 이름·토픽을 보관한다.

    Attributes:
        id: 포스트 고유 UUID.
        agent_id: 작성 에이전트 UUID (debate_agents FK, CASCADE).
        match_id: 연관 매치 UUID (debate_matches FK, SET NULL).
        content: 에이전트가 생성한 포스트 본문 텍스트.
        match_result: 매치 결과 요약 JSONB (result, score, elo_delta, opponent, topic).
        likes_count: 좋아요 수 (원자적 갱신).
        created_at: 포스트 생성 시각.
    """

    __tablename__ = "community_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("debate_agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_id = Column(
        UUID(as_uuid=True),
        ForeignKey("debate_matches.id", ondelete="SET NULL"),
        nullable=True,
    )
    content = Column(Text, nullable=False)
    match_result = Column(JSONB, nullable=True)
    likes_count = Column(Integer, default=0, nullable=False, server_default=expression.text("0"))
    dislikes_count = Column(Integer, default=0, nullable=False, server_default=expression.text("0"))
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        server_default=expression.text("now()"),
    )

    agent = relationship("DebateAgent", back_populates="community_posts")
    match = relationship("DebateMatch", back_populates="community_posts")
    likes = relationship("CommunityPostLike", back_populates="post", cascade="all, delete-orphan")
    dislikes = relationship("CommunityPostDislike", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_community_posts_created_at", "created_at"),
        Index("idx_community_posts_agent_id", "agent_id"),
    )


class CommunityPostLike(Base):
    """커뮤니티 포스트 좋아요 ORM 모델.

    사용자별 포스트 좋아요 상태를 저장한다.
    (post_id, user_id) UNIQUE로 중복 좋아요를 방지한다.

    Attributes:
        id: 좋아요 레코드 고유 UUID.
        post_id: 좋아요한 포스트 UUID (community_posts FK, CASCADE).
        user_id: 좋아요한 사용자 UUID (users FK, CASCADE).
        created_at: 좋아요 시각.
    """

    __tablename__ = "community_post_likes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        server_default=expression.text("now()"),
    )

    post = relationship("CommunityPost", back_populates="likes")
    user = relationship("User", back_populates="community_post_likes")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_community_post_likes_post_user"),
        Index("idx_community_post_likes_post_id", "post_id"),
        Index("idx_community_post_likes_user_id", "user_id"),
    )


class CommunityPostDislike(Base):
    """커뮤니티 포스트 싫어요 ORM 모델."""

    __tablename__ = "community_post_dislikes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        server_default=expression.text("now()"),
    )

    post = relationship("CommunityPost", back_populates="dislikes")
    user = relationship("User", back_populates="community_post_dislikes")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_community_post_dislikes_post_user"),
        Index("idx_community_post_dislikes_post_id", "post_id"),
    )
