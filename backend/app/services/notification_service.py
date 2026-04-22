"""알림 서비스.

매치 이벤트, 예측투표 결과, 신규 팔로워 알림을 생성하고 조회한다.
create_bulk는 실패해도 예외를 전파하지 않아 알림 오류가 핵심 흐름을 중단하지 않도록 한다.
"""

import logging
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch, DebateMatchPrediction
from app.models.user import User
from app.models.user_notification import UserNotification

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: UUID,
        type: str,
        title: str,
        body: str | None,
        link: str | None,
    ) -> UserNotification:
        """알림 1건 생성."""
        notification = UserNotification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            link=link,
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def create_bulk(self, notifications: list[dict]) -> None:
        """알림 N건 일괄 생성. 실패 시 로깅만 하고 예외를 전파하지 않는다."""
        if not notifications:
            return
        try:
            objs = [UserNotification(**n) for n in notifications]
            self.db.add_all(objs)
            await self.db.flush()
        except Exception:
            await self.db.rollback()  # flush 실패 시 세션 PendingRollback 상태 복구
            logger.exception("create_bulk failed: count=%d", len(notifications))

    async def get_list(
        self,
        user_id: UUID,
        offset: int,
        limit: int,
        unread_only: bool = False,
    ) -> tuple[list[UserNotification], int, int]:
        """알림 목록 (created_at DESC). 페이지네이션.

        Returns: (items, total, unread_count) — 단일 집계 쿼리로 이중 COUNT 제거.
        """
        base_where = [UserNotification.user_id == user_id]
        if unread_only:
            base_where.append(UserNotification.is_read == False)  # noqa: E712

        # total과 unread_count를 단일 쿼리로 집계
        counts = await self.db.execute(
            select(
                func.count().label("total"),
                func.count().filter(UserNotification.is_read == False).label("unread"),  # noqa: E712
            ).where(and_(*base_where))
        )
        row = counts.one()
        total, unread_count = row.total, row.unread

        result = await self.db.execute(
            select(UserNotification)
            .where(and_(*base_where))
            .order_by(UserNotification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total or 0, unread_count or 0

    async def get_unread_count(self, user_id: UUID) -> int:
        """미읽기 알림 수."""
        count = await self.db.scalar(
            select(func.count()).select_from(UserNotification).where(
                and_(
                    UserNotification.user_id == user_id,
                    UserNotification.is_read == False,  # noqa: E712
                )
            )
        )
        return count or 0

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> None:
        """단건 읽음 처리. 소유권 체크 실패 시 PermissionError."""
        result = await self.db.execute(
            select(UserNotification).where(UserNotification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise ValueError("notification_not_found")
        if notification.user_id != user_id:
            raise PermissionError("not_owner")
        notification.is_read = True

    async def mark_all_read(self, user_id: UUID) -> int:
        """전체 읽음 처리. 변경 건수 반환."""
        result = await self.db.execute(
            update(UserNotification)
            .where(
                and_(
                    UserNotification.user_id == user_id,
                    UserNotification.is_read == False,  # noqa: E712
                )
            )
            .values(is_read=True)
        )
        return result.rowcount

    async def notify_match_event(self, match_id: UUID, event: str) -> None:
        """매치 시작/종료 시 양쪽 에이전트 팔로워들에게 알림 생성.

        팔로워가 없으면 DB 쿼리를 최소화하기 위해 조기 반환한다.
        """
        from app.services.follow_service import FollowService

        match_result = await self.db.execute(
            select(DebateMatch).where(DebateMatch.id == match_id)
        )
        match = match_result.scalar_one_or_none()
        if match is None:
            logger.warning("notify_match_event: match not found: %s", match_id)
            return

        agents_result = await self.db.execute(
            select(DebateAgent).where(
                DebateAgent.id.in_([match.agent_a_id, match.agent_b_id])
            )
        )
        agents_map = {a.id: a for a in agents_result.scalars().all()}
        agent_a = agents_map.get(match.agent_a_id)
        agent_b = agents_map.get(match.agent_b_id)

        follow_svc = FollowService(self.db)
        followers_a = await follow_svc.get_follower_user_ids("agent", match.agent_a_id)
        followers_b = await follow_svc.get_follower_user_ids("agent", match.agent_b_id)
        # 두 에이전트 모두 팔로우하는 사용자는 알림 1건만 받도록 중복 제거
        recipient_ids = set(followers_a) | set(followers_b)

        if not recipient_ids:
            return

        name_a = agent_a.name if agent_a else str(match.agent_a_id)
        name_b = agent_b.name if agent_b else str(match.agent_b_id)
        link = f"/debate/matches/{match_id}"

        if event == "match_started":
            title = "매치 시작"
            body = f"{name_a} vs {name_b}"
            notif_type = "match_started"
        elif event == "match_finished":
            title = "매치 종료"
            if match.winner_id is None:
                body = "무승부"
            elif match.winner_id == match.agent_a_id:
                body = f"{name_a} 승리!"
            else:
                body = f"{name_b} 승리!"
            notif_type = "match_finished"
        else:
            logger.warning("notify_match_event: unknown event '%s'", event)
            return

        notifications = [
            {"user_id": uid, "type": notif_type, "title": title, "body": body, "link": link}
            for uid in recipient_ids
        ]
        await self.create_bulk(notifications)

    async def notify_prediction_result(self, match_id: UUID) -> None:
        """예측투표 결과 확정 시 투표자에게 알림."""
        match_result = await self.db.execute(
            select(DebateMatch).where(DebateMatch.id == match_id)
        )
        match = match_result.scalar_one_or_none()
        if match is None:
            logger.warning("notify_prediction_result: match not found: %s", match_id)
            return

        predictions_result = await self.db.execute(
            select(DebateMatchPrediction).where(DebateMatchPrediction.match_id == match_id)
        )
        predictions = list(predictions_result.scalars().all())
        if not predictions:
            return

        agents_result = await self.db.execute(
            select(DebateAgent).where(
                DebateAgent.id.in_([match.agent_a_id, match.agent_b_id])
            )
        )
        agents_map = {a.id: a for a in agents_result.scalars().all()}
        agent_a = agents_map.get(match.agent_a_id)
        agent_b = agents_map.get(match.agent_b_id)

        name_a = agent_a.name if agent_a else str(match.agent_a_id)
        name_b = agent_b.name if agent_b else str(match.agent_b_id)
        link = f"/debate/matches/{match_id}"

        if match.winner_id is None:
            result_body = "무승부로 종료되었습니다."
        elif match.winner_id == match.agent_a_id:
            result_body = f"{name_a} 승리!"
        else:
            result_body = f"{name_b} 승리!"

        notifications = [
            {
                "user_id": p.user_id,
                "type": "prediction_result",
                "title": "예측 결과 확정",
                "body": result_body,
                "link": link,
            }
            for p in predictions
        ]
        await self.create_bulk(notifications)

    async def notify_new_follower(
        self, follower_id: UUID, target_type: str, target_id: UUID
    ) -> None:
        """새 팔로워 알림.

        - target_type='user': 대상 User에게 직접 알림
        - target_type='agent': DebateAgent.owner_id에게 알림
        """
        follower_result = await self.db.execute(
            select(User).where(User.id == follower_id)
        )
        follower = follower_result.scalar_one_or_none()
        follower_name = follower.nickname if follower else str(follower_id)

        if target_type == "user":
            recipient_id = target_id
            title = "새 팔로워"
            body = f"{follower_name}님이 회원님을 팔로우합니다."
            link = None
        elif target_type == "agent":
            agent_result = await self.db.execute(
                select(DebateAgent).where(DebateAgent.id == target_id)
            )
            agent = agent_result.scalar_one_or_none()
            if agent is None:
                logger.warning("notify_new_follower: agent not found: %s", target_id)
                return
            recipient_id = agent.owner_id
            title = "새 팔로워"
            body = f"{follower_name}님이 에이전트 '{agent.name}'을 팔로우합니다."
            link = f"/debate/agents/{target_id}"
        else:
            logger.warning("notify_new_follower: unknown target_type '%s'", target_type)
            return

        await self.create_bulk([
            {
                "user_id": recipient_id,
                "type": "new_follower",
                "title": title,
                "body": body,
                "link": link,
            }
        ])
