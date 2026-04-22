"""매칭 서비스. 큐 등록 + 준비 완료 버튼으로 매치 생성."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_password
from app.core.config import settings
from app.core.exceptions import QueueConflictError
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch, DebateMatchQueue
from app.models.debate_topic import DebateTopic
from app.models.user import User
from app.services.debate.agent_service import get_latest_version
from app.services.debate.broadcast import publish_queue_event
from app.services.debate.promotion_service import DebatePromotionService
from app.services.debate.season_service import DebateSeasonService

logger = logging.getLogger(__name__)


class DebateMatchingService:
    """큐 등록·취소, 준비 완료(ready_up), 매치 생성을 담당하는 매칭 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _purge_expired_entries(self) -> None:
        """만료된 큐 항목을 bulk DELETE로 정리한다.

        join_queue() 진입 시 호출되어 데드 엔트리를 정리한다.
        예외는 내부에서 처리하며 상위로 전파하지 않는다.
        """
        try:
            await self.db.execute(
                delete(DebateMatchQueue)
                .where(DebateMatchQueue.expires_at <= datetime.now(UTC))
                .execution_options(synchronize_session=False)
            )
            await self.db.flush()
        except Exception:
            logger.warning("만료 항목 purge 실패 — 큐 등록 계속 진행", exc_info=True)

    async def join_queue(self, user: User, topic_id: str, agent_id: str, password: str | None = None) -> dict:
        """에이전트를 매칭 큐에 등록한다.

        토픽 검증 → 소유권 확인 → API 키 확인 → 크레딧 검증 → 큐 INSERT 순서로 처리.
        상대가 이미 대기 중이면 양쪽에 opponent_joined SSE 이벤트를 발행한다.

        Args:
            user: 현재 인증된 사용자.
            topic_id: 등록할 토픽 UUID 문자열.
            agent_id: 참가시킬 에이전트 UUID 문자열.
            password: 비밀번호 보호 토픽인 경우 입력 비밀번호.

        Returns:
            status, position, (opponent_agent_id) 키를 포함한 dict.

        Raises:
            ValueError: 토픽 미존재, 비밀번호 불일치, 에이전트 미존재, 크레딧 부족 등.
            QueueConflictError: 동일 사용자/에이전트가 이미 다른 큐에 대기 중인 경우.
        """
        # 토픽 검증
        topic = await self.db.execute(
            select(DebateTopic).where(DebateTopic.id == topic_id)
        )
        topic = topic.scalar_one_or_none()
        if topic is None:
            raise ValueError("Topic not found")
        if topic.status != "open":
            raise ValueError("Topic is not open for matches")

        if topic.is_password_protected and (not password or not verify_password(password, topic.password_hash)):
            raise ValueError("비밀번호가 올바르지 않습니다")

        # 에이전트 소유권 검증 (admin/superadmin은 모든 에이전트 사용 가능)
        is_admin = user.role in ("admin", "superadmin")
        if is_admin:
            agent = await self.db.execute(select(DebateAgent).where(DebateAgent.id == agent_id))
        else:
            agent = await self.db.execute(
                select(DebateAgent).where(DebateAgent.id == agent_id, DebateAgent.owner_id == user.id)
            )
        agent = agent.scalar_one_or_none()
        if agent is None:
            raise ValueError("Agent not found or not owned by user")
        if not agent.is_active:
            raise ValueError("Agent is not active")

        # API 키 검증: local/BYOK/platform_credits는 통과, 나머지는 플랫폼 환경변수 키 존재 여부 확인
        if agent.provider != "local" and not agent.encrypted_api_key and not agent.use_platform_credits:
            # 플랫폼 fallback 키가 있으면 허용 (없으면 거부)
            provider_has_platform_key = {
                "openai": bool(settings.openai_api_key),
                "anthropic": bool(settings.anthropic_api_key),
                "google": bool(settings.google_api_key),
                "runpod": bool(settings.runpod_api_key),
            }.get(agent.provider, False)
            if not provider_has_platform_key:
                raise ValueError(
                    f"에이전트에 API 키가 설정되지 않았습니다. "
                    f"에이전트 설정에서 API 키를 입력하거나 '플랫폼 크레딧 사용'을 활성화하세요."
                )

        # 크레딧 사전 검증: BYOK 에이전트(자기 API 키)는 차감 없음, 나머지는 잔액 확인
        if settings.debate_credit_cost > 0 and settings.credit_system_enabled and not agent.encrypted_api_key:
            owner_result = await self.db.execute(
                select(User.credit_balance).where(User.id == agent.owner_id)
            )
            owner_balance = owner_result.scalar_one_or_none() or 0
            if owner_balance < settings.debate_credit_cost:
                raise ValueError(
                    f"크레딧이 부족합니다. 필요: {settings.debate_credit_cost}석, 현재: {owner_balance}석"
                )

        await self._purge_expired_entries()

        # 유저당 1개 큐만 허용 (admin 제외)
        if not is_admin:
            user_existing = await self.db.execute(
                select(DebateMatchQueue).where(DebateMatchQueue.user_id == user.id)
            )
            existing_user_entry = user_existing.scalar_one_or_none()
            # 이미 다른 에이전트로 대기 중이면 QueueConflictError — 프론트에서 기존 대기 취소 유도
            if existing_user_entry is not None:
                raise QueueConflictError(
                    "이미 다른 에이전트로 대기 중입니다. 기존 대기를 취소한 뒤 다시 시도하세요.",
                    str(existing_user_entry.topic_id),
                )

        # 에이전트가 어느 토픽이든 이미 대기 중인지 확인 (에이전트당 1개 토픽 제한)
        existing = await self.db.execute(
            select(DebateMatchQueue).where(
                DebateMatchQueue.agent_id == agent_id,
            )
        )
        existing_entry = existing.scalar_one_or_none()
        if existing_entry is not None:
            # 같은 토픽이면 단순 중복 — 다른 토픽이면 에이전트가 여러 토픽에 동시 참가 시도
            if str(existing_entry.topic_id) == str(topic_id):
                raise ValueError("이미 이 토픽 대기 중입니다.")
            raise QueueConflictError(
                "에이전트가 이미 다른 토픽 대기 중입니다. 기존 대기를 취소한 뒤 다시 시도하세요.",
                str(existing_entry.topic_id),
            )

        # 큐 등록
        entry = DebateMatchQueue(
            topic_id=topic_id,
            agent_id=agent_id,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.debate_queue_timeout_seconds),
        )
        self.db.add(entry)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            constraint = str(exc.orig)
            # race condition: 위 existing 체크 후 동시에 다른 요청이 먼저 INSERT한 경우
            if "uq_debate_queue_topic_agent" in constraint:
                raise ValueError("이미 이 토픽 대기 중입니다.") from exc
            raise ValueError("이미 대기 중인 항목이 있습니다. 잠시 후 다시 시도하세요.") from exc

        # 이미 대기 중인 다른 사용자 확인 (자기 매칭 방지)
        opponent_result = await self.db.execute(
            select(DebateMatchQueue)
            .where(
                DebateMatchQueue.topic_id == topic_id,
                DebateMatchQueue.agent_id != entry.agent_id,
                DebateMatchQueue.user_id != user.id,
            )
            .order_by(DebateMatchQueue.joined_at)
            .limit(1)
        )
        opponent_entry = opponent_result.scalar_one_or_none()

        await self.db.commit()

        # 큐에 상대가 대기 중이면 양방향 SSE 이벤트 발행 (ready_up 버튼 활성화 유도)
        if opponent_entry:
            # 상대에게 내가 입장했음을 알림
            await publish_queue_event(topic_id, str(opponent_entry.agent_id), "opponent_joined", {
                "opponent_agent_id": str(agent_id),
            })
            # 나에게도 상대가 있음을 알림
            await publish_queue_event(topic_id, str(agent_id), "opponent_joined", {
                "opponent_agent_id": str(opponent_entry.agent_id),
            })
            return {
                "status": "queued",
                "position": 1,
                "opponent_agent_id": str(opponent_entry.agent_id),
            }

        return {"status": "queued", "position": 1}

    async def ready_up(self, user: User, topic_id: str, agent_id: str) -> dict:
        """준비 완료 처리. 양쪽 모두 준비되면 매치 생성.

        ABBA 데드락 방지: 토픽의 모든 큐 항목을 PK 오름차순으로 한번에 잠금.
        두 concurrent 트랜잭션이 항상 동일한 잠금 순서를 사용하므로 교착 없음.
        """
        all_result = await self.db.execute(
            select(DebateMatchQueue)
            .where(DebateMatchQueue.topic_id == topic_id)
            .order_by(DebateMatchQueue.id)
            .with_for_update()
        )
        all_entries = all_result.scalars().all()

        my_entry = next(
            (e for e in all_entries if str(e.agent_id) == str(agent_id) and e.user_id == user.id),
            None,
        )
        # 현재 사용자가 큐에 없으면 ready_up 불가
        if my_entry is None:
            raise ValueError("Not in queue")

        opponent_entry = next(
            (e for e in all_entries if str(e.agent_id) != str(agent_id) and e.user_id != user.id),
            None,
        )

        # 이미 준비 완료 상태이면 멱등 처리 — 중복 요청에도 안전
        if my_entry.is_ready:
            await self.db.commit()  # FOR UPDATE 락 즉시 해제
            return {"status": "already_ready"}

        my_entry.is_ready = True
        await self.db.flush()

        # 상대가 아직 큐에 없으면 대기 상태로 반환 (카운트다운 미시작)
        if opponent_entry is None:
            await self.db.commit()
            return {"status": "ready", "waiting_for_opponent": True}

        if not opponent_entry.is_ready:
            # 첫 번째 준비 완료 → 10초 카운트다운 시작 이벤트를 양쪽에 발행
            await self.db.commit()
            await publish_queue_event(topic_id, str(my_entry.agent_id), "countdown_started", {
                "countdown_seconds": settings.debate_ready_countdown_seconds,
                "ready_agent_id": str(my_entry.agent_id),
            })
            await publish_queue_event(topic_id, str(opponent_entry.agent_id), "countdown_started", {
                "countdown_seconds": settings.debate_ready_countdown_seconds,
                "ready_agent_id": str(my_entry.agent_id),
            })
            return {
                "status": "ready",
                "waiting_for_opponent": False,
                "countdown_started": True,
                "opponent_agent_id": str(opponent_entry.agent_id),
            }

        # 양쪽 모두 준비 완료 → 매치 생성
        ver_a = await get_latest_version(self.db, my_entry.agent_id)
        ver_b = await get_latest_version(self.db, opponent_entry.agent_id)

        match = DebateMatch(
            topic_id=topic_id,
            agent_a_id=my_entry.agent_id,
            agent_b_id=opponent_entry.agent_id,
            agent_a_version_id=ver_a.id if ver_a else None,
            agent_b_version_id=ver_b.id if ver_b else None,
            status="pending",
        )

        # 활성 시즌이 있으면 season_id 태깅
        season_svc = DebateSeasonService(self.db)
        active_season = await season_svc.get_active_season()
        if active_season:
            match.season_id = active_season.id

        # commit 전 ID를 로컬 변수에 복사 — commit 후 detached 객체 접근 방어
        my_agent_id = str(my_entry.agent_id)
        opp_agent_id = str(opponent_entry.agent_id)

        # 시리즈 소속 매치인 경우 match_type / series_id 태깅
        # 두 에이전트 모두 활성 시리즈가 있을 수 있으므로 양쪽 확인 (첫 번째 우선)
        promo_svc = DebatePromotionService(self.db)
        for entry_agent_id in [my_agent_id, opp_agent_id]:
            series = await promo_svc.get_active_series(entry_agent_id)
            # match.series_id가 None인 경우에만 태깅 — 두 에이전트 모두 시리즈 중이면 첫 번째만 연결
            if series and match.series_id is None:
                match.match_type = series.series_type
                match.series_id = series.id
                break  # 첫 번째 우선 — 불필요한 두 번째 DB 쿼리 방지

        self.db.add(match)
        await self.db.delete(my_entry)
        await self.db.delete(opponent_entry)
        await self.db.commit()
        await self.db.refresh(match)

        logger.info("Match created (ready-up): %s (topic=%s)", match.id, topic_id)

        await publish_queue_event(topic_id, my_agent_id, "matched", {
            "match_id": str(match.id),
            "opponent_agent_id": opp_agent_id,
            "auto_matched": False,
        })
        await publish_queue_event(topic_id, opp_agent_id, "matched", {
            "match_id": str(match.id),
            "opponent_agent_id": my_agent_id,
            "auto_matched": False,
        })

        return {"status": "matched", "match_id": str(match.id)}
