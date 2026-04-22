"""팔로우 서비스.

사용자 → 사용자/에이전트 팔로우 관계를 관리한다.
target_type='agent'는 debate_agents, target_type='user'는 users 테이블의 존재 여부를 검증한다.
"""

import logging
from uuid import UUID

from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_agent import DebateAgent
from app.models.user import User
from app.models.user_follow import UserFollow

logger = logging.getLogger(__name__)


class FollowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def follow(self, follower_id: UUID, target_type: str, target_id: UUID) -> UserFollow:
        """팔로우 생성.

        - target_type에 따라 DebateAgent 또는 User 존재 확인 (없으면 ValueError)
        - 자기 자신 팔로우 방지 (target_type='user', target_id==follower_id → ValueError)
        - 중복 시 IntegrityError → ValueError('already_following') 변환
        """
        if target_type == "user":
            if target_id == follower_id:
                raise ValueError("self_follow")
            exists = await self.db.scalar(
                select(func.count()).select_from(User).where(User.id == target_id)
            )
            if not exists:
                raise ValueError("target_not_found")
        elif target_type == "agent":
            exists = await self.db.scalar(
                select(func.count()).select_from(DebateAgent).where(DebateAgent.id == target_id)
            )
            if not exists:
                raise ValueError("target_not_found")
        else:
            raise ValueError("invalid_target_type")

        follow = UserFollow(
            follower_id=follower_id,
            target_type=target_type,
            target_id=target_id,
        )
        self.db.add(follow)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("already_following") from None
        return follow

    async def unfollow(self, follower_id: UUID, target_type: str, target_id: UUID) -> None:
        """언팔로우. 미존재 시 ValueError('not_following')."""
        result = await self.db.execute(
            delete(UserFollow).where(
                and_(
                    UserFollow.follower_id == follower_id,
                    UserFollow.target_type == target_type,
                    UserFollow.target_id == target_id,
                )
            )
        )
        if result.rowcount == 0:
            raise ValueError("not_following")

    async def get_following(
        self,
        user_id: UUID,
        target_type: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[UserFollow], int]:
        """내 팔로우 목록 + 전체 수. target_type 필터 선택적."""
        base_where = [UserFollow.follower_id == user_id]
        if target_type is not None:
            base_where.append(UserFollow.target_type == target_type)

        total = await self.db.scalar(
            select(func.count()).select_from(UserFollow).where(and_(*base_where))
        )
        result = await self.db.execute(
            select(UserFollow)
            .where(and_(*base_where))
            .order_by(UserFollow.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total or 0

    async def get_follower_count(self, target_type: str, target_id: UUID) -> int:
        """특정 대상의 팔로워 수."""
        count = await self.db.scalar(
            select(func.count()).select_from(UserFollow).where(
                and_(
                    UserFollow.target_type == target_type,
                    UserFollow.target_id == target_id,
                )
            )
        )
        return count or 0

    async def is_following(self, follower_id: UUID, target_type: str, target_id: UUID) -> bool:
        """팔로우 여부 확인."""
        count = await self.db.scalar(
            select(func.count()).select_from(UserFollow).where(
                and_(
                    UserFollow.follower_id == follower_id,
                    UserFollow.target_type == target_type,
                    UserFollow.target_id == target_id,
                )
            )
        )
        return (count or 0) > 0

    async def get_follower_user_ids(self, target_type: str, target_id: UUID) -> list[UUID]:
        """특정 대상의 팔로워 user_id 목록 (알림 발송용)."""
        result = await self.db.execute(
            select(UserFollow.follower_id).where(
                and_(
                    UserFollow.target_type == target_type,
                    UserFollow.target_id == target_id,
                )
            )
        )
        return list(result.scalars().all())
