"""토픽 CRUD, 스케줄 상태 자동 갱신, Redis 캐싱 서비스."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash  # 비밀번호 보호 토픽 해시 생성
from app.core.redis import get_redis  # 스케줄 동기화 분산 락
from app.models.debate_match import DebateMatch, DebateMatchQueue
from app.models.debate_topic import DebateTopic
from app.models.user import User
from app.schemas.debate_topic import TopicCreate, TopicUpdate, TopicUpdatePayload

logger = logging.getLogger(__name__)

_TOPIC_SYNC_REDIS_KEY = "debate:topic_sync:last_at"
_TOPIC_SYNC_INTERVAL_SECS = 60


class DebateTopicService:
    """토론 주제(토픽) 생성·조회·수정·삭제 및 스케줄 상태 자동 갱신 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_topic(self, data: TopicCreate, user: User) -> DebateTopic:
        """토론 주제 생성. 스케줄 필드는 모든 사용자가 설정 가능, 관리자 여부는 is_admin_topic 플래그로만 구분."""
        from app.core.config import settings

        is_admin = user.role in ("admin", "superadmin")
        now = datetime.now(UTC)

        # 일반 사용자 일일 등록 한도 검사 (관리자는 제한 없음)
        if not is_admin:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            count_result = await self.db.execute(
                select(func.count(DebateTopic.id)).where(
                    DebateTopic.created_by == user.id,
                    DebateTopic.created_at >= today_start,
                )
            )
            today_count = count_result.scalar() or 0
            if today_count >= settings.debate_daily_topic_limit:
                raise ValueError(
                    f"일일 토론 주제 등록 한도({settings.debate_daily_topic_limit}개)에 도달했습니다."
                    " 내일 다시 시도하세요."
                )

        # 시작 시각이 미래이면 scheduled, 아니면 open
        initial_status = "scheduled" if data.scheduled_start_at and data.scheduled_start_at > now else "open"

        hashed_password = None
        is_password_protected = False
        if data.password:
            hashed_password = get_password_hash(data.password)
            is_password_protected = True

        topic = DebateTopic(
            title=data.title,
            description=data.description,
            mode=data.mode,
            max_turns=data.max_turns,
            turn_token_limit=data.turn_token_limit,
            tools_enabled=data.tools_enabled,
            scheduled_start_at=data.scheduled_start_at,
            scheduled_end_at=data.scheduled_end_at,
            is_admin_topic=is_admin,
            status=initial_status,
            created_by=user.id,
            is_password_protected=is_password_protected,
            password_hash=hashed_password,
        )
        self.db.add(topic)
        await self.db.commit()
        await self.db.refresh(topic)
        return topic

    async def get_topic(self, topic_id: str) -> DebateTopic | None:
        """토픽 단건 조회.

        Args:
            topic_id: 토픽 UUID 문자열.

        Returns:
            DebateTopic 객체. 존재하지 않으면 None.
        """
        result = await self.db.execute(
            select(DebateTopic).where(DebateTopic.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def list_topics(
        self,
        status: str | None = None,
        sort: str = "recent",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """토픽 목록 조회. 집계 서브쿼리로 N+1 방지.

        sort: 'recent'(최신순) | 'popular_week'(이번 주 매치 수) | 'queue'(대기 많은 순) | 'matches'(전체 매치 많은 순)
        """
        await self._sync_scheduled_topics()

        # 집계 서브쿼리로 queue_count·match_count를 한 번의 JOIN으로 해결
        queue_subq = (
            select(DebateMatchQueue.topic_id, func.count(DebateMatchQueue.id).label("q_cnt"))
            .group_by(DebateMatchQueue.topic_id)
            .subquery()
        )
        match_subq = (
            select(DebateMatch.topic_id, func.count(DebateMatch.id).label("m_cnt"))
            .where(DebateMatch.is_test.is_(False))
            .group_by(DebateMatch.topic_id)
            .subquery()
        )

        query = (
            select(
                DebateTopic,
                User.nickname.label("creator_nickname"),
                func.coalesce(queue_subq.c.q_cnt, 0).label("queue_count"),
                func.coalesce(match_subq.c.m_cnt, 0).label("match_count"),
            )
            .outerjoin(User, DebateTopic.created_by == User.id)
            .outerjoin(queue_subq, DebateTopic.id == queue_subq.c.topic_id)
            .outerjoin(match_subq, DebateTopic.id == match_subq.c.topic_id)
        )
        count_query = select(func.count(DebateTopic.id))

        if status:
            query = query.where(DebateTopic.status == status)
            count_query = count_query.where(DebateTopic.status == status)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        if sort == "popular_week":
            from datetime import timedelta

            week_ago = datetime.now(UTC) - timedelta(days=7)
            popular_subq = (
                select(DebateMatch.topic_id, func.count(DebateMatch.id).label("weekly_cnt"))
                .where(DebateMatch.created_at >= week_ago)
                .group_by(DebateMatch.topic_id)
                .subquery()
            )
            query = (
                query.outerjoin(popular_subq, DebateTopic.id == popular_subq.c.topic_id)
                .order_by(func.coalesce(popular_subq.c.weekly_cnt, 0).desc(), DebateTopic.created_at.desc())
            )
        elif sort == "queue":
            # 현재 대기 인원 많은 순
            query = query.order_by(func.coalesce(queue_subq.c.q_cnt, 0).desc(), DebateTopic.created_at.desc())
        elif sort == "matches":
            # 전체 매치 수 많은 순
            query = query.order_by(func.coalesce(match_subq.c.m_cnt, 0).desc(), DebateTopic.created_at.desc())
        else:
            # recent (기본)
            query = query.order_by(DebateTopic.created_at.desc())

        result = await self.db.execute(query.offset((page - 1) * page_size).limit(page_size))
        rows = result.all()

        items = []
        for row in rows:
            topic = row[0]
            creator_nickname = row[1]
            queue_count = row[2]
            match_count = row[3]
            items.append({
                "id": str(topic.id),
                "title": topic.title,
                "description": topic.description,
                "mode": topic.mode,
                "status": topic.status,
                "max_turns": topic.max_turns,
                "turn_token_limit": topic.turn_token_limit,
                "scheduled_start_at": topic.scheduled_start_at,
                "scheduled_end_at": topic.scheduled_end_at,
                "is_admin_topic": topic.is_admin_topic,
                "is_password_protected": topic.is_password_protected,
                "tools_enabled": topic.tools_enabled,
                "queue_count": queue_count,
                "match_count": match_count,
                "created_at": topic.created_at,
                "updated_at": topic.updated_at,
                "created_by": topic.created_by,
                "creator_nickname": creator_nickname,
            })

        return items, total

    async def update_topic(self, topic_id: str, data: TopicUpdate) -> DebateTopic:
        """관리자 전용 토픽 수정. 미존재 시 ValueError.

        Args:
            topic_id: 수정할 토픽 UUID 문자열.
            data: 수정할 필드만 포함하는 TopicUpdate 스키마.

        Returns:
            수정된 DebateTopic 객체.

        Raises:
            ValueError: 토픽이 존재하지 않는 경우.
        """
        result = await self.db.execute(
            select(DebateTopic).where(DebateTopic.id == topic_id)
        )
        topic = result.scalar_one_or_none()
        if topic is None:
            raise ValueError("Topic not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(topic, field, value)

        await self.db.commit()
        await self.db.refresh(topic)
        return topic

    async def update_topic_by_user(
        self, topic_id: UUID, user_id: UUID, payload: TopicUpdatePayload
    ) -> DebateTopic:
        """주제 작성자가 자신의 주제를 수정. 미존재 시 ValueError, 권한 없으면 PermissionError."""
        topic = await self.db.get(DebateTopic, topic_id)
        if not topic:
            raise ValueError("Topic not found")
        if topic.created_by != user_id:
            raise PermissionError("Not the topic creator")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(topic, field, value)

        await self.db.commit()
        await self.db.refresh(topic)
        return topic

    async def delete_topic(self, topic_id: str) -> None:
        """토픽 삭제 (매치가 없는 경우만 허용). 대기 큐를 먼저 정리."""
        from sqlalchemy import delete as sa_delete

        result = await self.db.execute(
            select(DebateTopic).where(DebateTopic.id == topic_id)
        )
        topic = result.scalar_one_or_none()
        if topic is None:
            raise ValueError("Topic not found")

        match_count = await self.count_matches(topic.id)
        if match_count > 0:
            raise ValueError(
                f"진행된 매치가 {match_count}개 있어 삭제할 수 없습니다. "
                "종료 처리 후 매치가 없을 때 삭제 가능합니다."
            )

        # 대기 큐 먼저 제거
        await self.db.execute(
            sa_delete(DebateMatchQueue).where(DebateMatchQueue.topic_id == topic.id)
        )
        await self.db.delete(topic)
        await self.db.commit()

    async def delete_topic_by_user(self, topic_id: UUID, user_id: UUID) -> None:
        """주제 작성자가 자신의 주제를 삭제. 진행 중 매치가 있으면 ValueError(409용)."""
        from sqlalchemy import delete as sa_delete

        topic = await self.db.get(DebateTopic, topic_id)
        if not topic:
            raise ValueError("Topic not found")
        if topic.created_by != user_id:
            raise PermissionError("Not the topic creator")

        active_count_result = await self.db.execute(
            select(func.count(DebateMatch.id)).where(
                DebateMatch.topic_id == topic_id,
                DebateMatch.status == "in_progress",
            )
        )
        active_matches = active_count_result.scalar() or 0
        if active_matches > 0:
            raise ValueError(f"진행 중인 매치가 {active_matches}개 있어 삭제할 수 없습니다.")

        await self.db.execute(
            sa_delete(DebateMatchQueue).where(DebateMatchQueue.topic_id == topic_id)
        )
        await self.db.delete(topic)
        await self.db.commit()

    async def _sync_scheduled_topics(self) -> None:
        """scheduled_start_at/end_at 기준으로 status 자동 갱신.

        Redis SET NX EX 패턴으로 멀티 워커 환경에서도 60초 이내 재실행 방지.
        Redis 장애 시에는 매번 실행(폴백).
        """
        try:
            r = await get_redis()
            # SET NX EX: 키가 없을 때만 설정 → 이미 있으면 다른 워커가 처리 중
            acquired = await r.set(_TOPIC_SYNC_REDIS_KEY, "1", nx=True, ex=_TOPIC_SYNC_INTERVAL_SECS)
            if not acquired:
                return
        except Exception:
            logger.debug("Redis unavailable for topic sync throttle, proceeding without lock")

        now = datetime.now(UTC)

        # scheduled → open (시작 시각 도달)
        await self.db.execute(
            update(DebateTopic)
            .where(
                DebateTopic.status == "scheduled",
                DebateTopic.scheduled_start_at <= now,
            )
            .values(status="open")
        )

        # open/in_progress → closed (종료 시각 초과)
        await self.db.execute(
            update(DebateTopic)
            .where(
                DebateTopic.status.in_(["open", "in_progress"]),
                DebateTopic.scheduled_end_at.isnot(None),
                DebateTopic.scheduled_end_at <= now,
            )
            .values(status="closed")
        )

        await self.db.commit()

    async def count_queue(self, topic_id) -> int:
        """토픽의 현재 대기 큐 항목 수를 반환.

        Args:
            topic_id: 토픽 UUID (str 또는 UUID 모두 허용).

        Returns:
            현재 대기 중인 에이전트 수.
        """
        result = await self.db.execute(
            select(func.count(DebateMatchQueue.id)).where(DebateMatchQueue.topic_id == topic_id)
        )
        return result.scalar() or 0

    async def count_matches(self, topic_id) -> int:
        """토픽의 정식 매치 수 반환 (테스트 매치 제외).

        Args:
            topic_id: 토픽 UUID (str 또는 UUID 모두 허용).

        Returns:
            해당 토픽에서 진행된 정식 매치 수.
        """
        result = await self.db.execute(
            select(func.count(DebateMatch.id)).where(
                DebateMatch.topic_id == topic_id,
                DebateMatch.is_test.is_(False),
            )
        )
        return result.scalar() or 0
