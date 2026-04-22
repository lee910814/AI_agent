"""토론 엔진. 비동기 백그라운드 태스크로 매치를 실행."""

import asyncio
import logging
import math
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from app.models.user import User
from app.schemas.debate_ws import WSMatchReady
from app.services.debate.broadcast import publish_event
from app.services.debate.control_plane import OrchestrationControlPlane
from app.services.debate.debate_formats import (
    TurnLoopResult,
    _log_orchestrator_usage,  # 테스트 import 경로 유지 — debate_formats에서 re-export
    get_format_runner,
)
from app.services.debate.format_1v1 import run_turns_1v1
from app.services.debate.format_multi import run_turns_multi  # noqa: F401 — get_format_runner 경유
from app.services.debate.exceptions import MatchVoidError
from app.services.debate.finalizer import MatchFinalizer
from app.services.debate.forfeit import ForfeitError, ForfeitHandler
from app.services.debate.helpers import (
    _resolve_api_key,
)
from app.services.debate.judge import DebateJudge
from app.services.debate.orchestrator import DebateOrchestrator
from app.services.debate.turn_executor import TurnExecutor
from app.services.debate.ws_manager import WSConnectionManager
from app.services.llm.inference_client import InferenceClient

logger = logging.getLogger(__name__)


def _calculate_required_credits(
    agent: DebateAgent,
    models_map: dict,
    max_turns: int,
    turn_token_limit: int,
) -> int:
    """에이전트 모델 기준 필요 크레딧을 산정한다 (테스트 가능한 순수 함수).

    예상 토큰 = max_turns × turn_token_limit × 1.5 (입력 토큰 누적 대비 버퍼).
    리뷰·판정 토큰은 포함하지 않는다.

    Args:
        agent: 크레딧 산정 대상 에이전트.
        models_map: model_id → LLMModel 매핑 dict (배치 조회 결과).
        max_turns: 토픽의 최대 턴 수.
        turn_token_limit: 턴당 최대 출력 토큰 수.

    Returns:
        필요 크레딧 수 (정수, 올림).
    """
    model = models_map.get(agent.model_id)
    if model is None:
        raise ValueError(
            f"Model '{agent.model_id}' not found in llm_models — "
            f"cannot calculate required credits for agent {agent.id}. "
            "Register the model in llm_models table or disable credit system."
        )
    return math.ceil(
        max_turns * turn_token_limit * settings.debate_credit_buffer_ratio * model.credit_per_1k_tokens / 1000
    )


class CreditInsufficientError(Exception):
    """크레딧 부족 — credit_insufficient SSE가 이미 발행됐으며, run_debate에서 error SSE로 매치 종료를 추가 알림."""


# 상단 import로 sub-module 심볼을 이 네임스페이스에 바인딩 — 테스트 import 경로 보호
# (from app.services.debate.engine import _resolve_api_key 등이 계속 동작)
__all__ = ["run_debate", "DebateEngine"]


# ── 테스트 하위 호환 래퍼 ──────────────────────────────────────────────────────
# 기존 테스트가 engine 모듈에서 직접 import하는 경로를 유지한다.
# 향후 테스트를 turn_executor / formats 모듈 경로로 마이그레이션하면 제거 가능.


async def _execute_turn_with_retry(
    db: AsyncSession,
    client: InferenceClient,
    match: DebateMatch,
    topic: DebateTopic,
    turn_number: int,
    speaker: str,
    agent: DebateAgent,
    version: DebateAgentVersion | None,
    api_key: str,
    my_claims: list[str],
    opponent_claims: list[str],
    my_accumulated_penalty: int = 0,
    event_meta: dict | None = None,
) -> DebateTurnLog | None:
    """TurnExecutor.execute_with_retry 래퍼 — 테스트 import 경로 유지."""
    executor = TurnExecutor(client, db)
    return await executor.execute_with_retry(
        match,
        topic,
        turn_number,
        speaker,
        agent,
        version,
        api_key,
        my_claims,
        opponent_claims,
        my_accumulated_penalty=my_accumulated_penalty,
        event_meta=event_meta,
    )


# 하위 호환 래퍼 — formats.run_turns_1v1로 마이그레이션 후 제거 예정


async def _run_turn_loop(
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    version_a: DebateAgentVersion | None,
    version_b: DebateAgentVersion | None,
    api_key_a: str,
    api_key_b: str,
    client: InferenceClient,
    orchestrator: DebateOrchestrator,
    model_cache: dict,
    usage_batch: list,
    parallel: bool,
    control_plane: OrchestrationControlPlane | None = None,
) -> tuple[list[str], list[str], int, int]:
    """formats.run_turns_1v1 위임 래퍼 — 테스트 import 경로 유지."""
    executor = TurnExecutor(client, db)
    result = await run_turns_1v1(
        executor,
        orchestrator,
        db,
        match,
        topic,
        agent_a,
        agent_b,
        version_a,
        version_b,
        api_key_a,
        api_key_b,
        model_cache,
        usage_batch,
        parallel,
        control_plane,
    )
    return result.claims_a, result.claims_b, result.total_penalty_a, result.total_penalty_b


# ── DebateEngine 클래스 ────────────────────────────────────────────────────────


class DebateEngine:
    """매치 실행 오케스트레이터 — 엔티티 로드 + 포맷 dispatch + finalize."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run(self, match_id: str) -> None:
        """진입점. 엔티티 로드 → 크레딧 차감 → 로컬 에이전트 대기 → 포맷 runner → 판정 → 후처리."""
        match, topic, agent_a, agent_b, version_a, version_b = await self._load_entities(match_id)

        # 크레딧 차감을 WebSocket 대기 전에 수행 — 잔액 부족 시 대기 시간 낭비 방지
        await self._deduct_credits(match, topic, agent_a, agent_b)

        await self._wait_for_local_agents(match, topic, agent_a, agent_b)

        if match.status == "forfeit":
            # 로컬 에이전트 접속 실패로 몰수패 처리 — 선차감 크레딧 환불 후 종료
            await self._refund_credits(match)
            return

        # is_test 매치는 플랫폼 크레딧으로 강제 실행
        use_platform = match.is_test
        api_key_a = _resolve_api_key(agent_a, force_platform=use_platform)
        api_key_b = _resolve_api_key(agent_b, force_platform=use_platform)

        match.status = "in_progress"
        match.started_at = datetime.now(UTC)
        await self.db.commit()
        try:
            await publish_event(str(match.id), "started", {"match_id": str(match.id)})
        except Exception:
            logger.warning("started SSE failed for match %s — continuing", match.id)

        async with InferenceClient() as client:
            await self._run_with_client(
                client, match, topic, agent_a, agent_b, version_a, version_b, api_key_a, api_key_b
            )

    async def _load_entities(
        self, match_id: str
    ) -> tuple[
        DebateMatch, DebateTopic, DebateAgent, DebateAgent, DebateAgentVersion | None, DebateAgentVersion | None
    ]:
        """매치 실행에 필요한 모든 엔티티를 병렬 조회한다.

        Args:
            match_id: 조회할 매치 UUID 문자열.

        Returns:
            (match, topic, agent_a, agent_b, version_a, version_b) 튜플.

        Raises:
            ValueError: 매치·토픽·에이전트 중 하나라도 미존재 시.
        """
        result = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = result.scalar_one_or_none()
        if match is None:
            raise ValueError(f"Match {match_id} not found")

        # SQLAlchemy AsyncSession은 동시 await를 허용하지 않으므로 순차 조회
        topic_result = await self.db.execute(select(DebateTopic).where(DebateTopic.id == match.topic_id))
        agents_res = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id.in_([match.agent_a_id, match.agent_b_id]))
        )

        topic = topic_result.scalar_one_or_none()
        if topic is None:
            raise ValueError(f"Topic {match.topic_id} not found for match {match.id}")

        agents_map = {str(a.id): a for a in agents_res.scalars().all()}
        agent_a = agents_map.get(str(match.agent_a_id))
        agent_b = agents_map.get(str(match.agent_b_id))
        if agent_a is None:
            raise ValueError(f"Agent {match.agent_a_id} not found for match {match.id}")
        if agent_b is None:
            raise ValueError(f"Agent {match.agent_b_id} not found for match {match.id}")

        version_ids = [v for v in [match.agent_a_version_id, match.agent_b_version_id] if v is not None]
        versions_map: dict = {}
        if version_ids:
            versions_res = await self.db.execute(
                select(DebateAgentVersion).where(DebateAgentVersion.id.in_(version_ids))
            )
            versions_map = {str(v.id): v for v in versions_res.scalars().all()}
        version_a = versions_map.get(str(match.agent_a_version_id)) if match.agent_a_version_id else None
        version_b = versions_map.get(str(match.agent_b_version_id)) if match.agent_b_version_id else None

        return match, topic, agent_a, agent_b, version_a, version_b

    async def _wait_for_local_agents(
        self,
        match: DebateMatch,
        topic: DebateTopic,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
    ) -> None:
        """로컬 에이전트가 있으면 WebSocket 접속을 대기한다.

        접속 실패 시 ForfeitHandler.handle_disconnect()를 호출하고
        match.status를 'forfeit'으로 변경한다. 이후 run()에서 forfeit 상태를 감지해 종료.

        Args:
            match: 대기 대상 매치.
            topic: 토론 주제 (match_ready 메시지용).
            agent_a: A측 에이전트.
            agent_b: B측 에이전트.
        """
        ws_manager = WSConnectionManager.get_instance()
        has_local = agent_a.provider == "local" or agent_b.provider == "local"
        if not has_local:
            return

        match.status = "waiting_agent"
        await self.db.commit()
        await publish_event(str(match.id), "waiting_agent", {"match_id": str(match.id)})

        local_agents = [
            (agent, side) for agent, side in [(agent_a, "agent_a"), (agent_b, "agent_b")] if agent.provider == "local"
        ]

        async def _try_connect(agent: DebateAgent, side: str) -> bool:
            connect_timeout = (
                settings.debate_agent_connect_timeout_tool
                if getattr(agent, "tools_enabled", False)
                else settings.debate_agent_connect_timeout
            )
            for attempt in range(1, settings.debate_agent_connect_retries + 1):
                if await ws_manager.wait_for_connection(agent.id, connect_timeout):
                    return True
                logger.warning(
                    "Agent %s connect attempt %d/%d failed for match %s",
                    agent.name,
                    attempt,
                    settings.debate_agent_connect_retries,
                    match.id,
                )
            return False

        # 로컬 에이전트가 여럿이면 병렬 대기 — 순차 시 최대 N×90초 낭비 방지
        results = await asyncio.gather(*[_try_connect(agent, side) for agent, side in local_agents])

        for (agent, side), connected in zip(local_agents, results, strict=False):
            if not connected:
                winner_agent = agent_b if side == "agent_a" else agent_a
                await ForfeitHandler(self.db).handle_disconnect(match, agent, winner_agent, side)
                # handle_disconnect()가 match.status = "forfeit" + commit() 처리
                return

        # 모든 로컬 에이전트 접속 완료 — match_ready 전송
        for agent, side in local_agents:
            opponent = agent_b if side == "agent_a" else agent_a
            await ws_manager.send_match_ready(
                agent.id,
                WSMatchReady(
                    match_id=match.id,
                    topic_title=topic.title,
                    opponent_name=opponent.name,
                    your_side=side,
                ),
            )

    async def _deduct_credits(
        self,
        match: DebateMatch,
        topic: DebateTopic,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
    ) -> None:
        """플랫폼 크레딧 사용 에이전트의 크레딧 차감.

        필요 크레딧은 모델별 credit_per_1k_tokens × 예상 토큰 수로 동적 산정.
        예상 토큰 = max_turns × turn_token_limit × 1.5 (입력 토큰 누적 대비 버퍼)
        리뷰/판정 등 플랫폼 오케스트레이션 토큰은 포함하지 않음.
        """
        if not settings.credit_system_enabled:
            return
        if match.is_test:
            return

        # 에이전트별 모델 조회 후 필요 크레딧 계산
        model_ids = {agent_a.model_id, agent_b.model_id}
        models_res = await self.db.execute(select(LLMModel).where(LLMModel.model_id.in_(model_ids)))
        models_map = {m.model_id: m for m in models_res.scalars().all()}

        # A 차감 후 B 실패 시 보상 롤백을 위해 성공한 차감을 추적한다
        deducted: list[tuple[DebateAgent, int]] = []

        for agent in (agent_a, agent_b):
            if not agent.use_platform_credits:
                continue
            required = _calculate_required_credits(agent, models_map, topic.max_turns, topic.turn_token_limit)
            deduct_result = await self.db.execute(
                update(User)
                .where(User.id == agent.owner_id, User.credit_balance >= required)
                .values(credit_balance=User.credit_balance - required)
                .returning(User.credit_balance)
            )
            if deduct_result.fetchone() is None:
                # 이미 차감된 에이전트 크레딧 보상 복원 — 외부 rollback 의존 제거
                if deducted:
                    prev_agent, prev_amount = deducted[0]
                    await self.db.execute(
                        update(User)
                        .where(User.id == prev_agent.owner_id)
                        .values(credit_balance=User.credit_balance + prev_amount)
                    )
                    match.credits_deducted = None
                    await self.db.commit()

                message = f"에이전트 '{agent.name}' 소유자의 크레딧이 부족합니다 (필요: {required}석)"
                # 보상 commit 이후 발행 — 클라이언트가 DB 반영 전 이벤트를 받지 않도록 한다
                await publish_event(
                    str(match.id),
                    "credit_insufficient",
                    {
                        "agent_id": str(agent.id),
                        "agent_name": agent.name,
                        "required": required,
                        "message": message,
                        "match_status": "error",
                    },
                )
                # credit_insufficient SSE를 이미 발행했으므로 error SSE 재발행 방지용 전용 예외
                raise CreditInsufficientError(message)

            # 차감 성공 시 누적 기록 — _refund_credits가 이 값을 참조해 환불 금액을 결정한다
            match.credits_deducted = (match.credits_deducted or 0) + required
            deducted.append((agent, required))

        await self.db.commit()

    async def _void_match(self, match: DebateMatch, reason: str) -> None:
        """매치를 error 상태로 전환하고 SSE로 알린다.

        Args:
            match: 상태를 변경할 매치 객체.
            reason: error 사유 문자열 (match_void SSE 페이로드에 포함).
        """
        match.status = "error"
        match.error_reason = reason
        await self.db.commit()
        await publish_event(str(match.id), "match_void", {"reason": reason})

    async def _refund_credits(self, match: DebateMatch) -> None:
        """선차감 크레딧을 두 참가자에게 자동 환불한다.

        match.credits_deducted가 0이거나 None이면 즉시 반환.
        use_platform_credits=True인 에이전트 소유자들에게만 균등 환불.
        credits_deducted는 _deduct_credits()에서 차감 시 누적 기록되므로 이 값이 신뢰할 수 있다.

        Args:
            match: 환불 대상 매치. credits_deducted 필드를 참조한다.
        """
        if not match.credits_deducted:
            return
        agents_res = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id.in_([match.agent_a_id, match.agent_b_id]))
        )
        agents = agents_res.scalars().all()
        owner_ids = list({a.owner_id for a in agents if a.use_platform_credits})
        if not owner_ids:
            # credits_deducted > 0인데 환불 대상이 없으면 데이터 불일치 — 경고만 남기고 진행한다
            logger.warning(
                "Match %s: credits_deducted=%s but no use_platform_credits agents found — skipping refund",
                match.id,
                match.credits_deducted,
            )
            return
        # use_platform_credits 에이전트 소유자 수로 나눠 균등 환불 (동일 owner 양쪽 소유 시 한 번만 환불)
        refund_per_owner = match.credits_deducted / len(owner_ids)
        await self.db.execute(
            update(User).where(User.id.in_(owner_ids)).values(credit_balance=User.credit_balance + refund_per_owner)
        )
        await self.db.commit()

    async def _run_with_client(
        self,
        client: InferenceClient,
        match: DebateMatch,
        topic: DebateTopic,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
        version_a: DebateAgentVersion | None,
        version_b: DebateAgentVersion | None,
        api_key_a: str,
        api_key_b: str,
    ) -> None:
        """InferenceClient를 이용해 포맷별 턴 루프를 실행하고 최종 판정·후처리를 수행한다.

        MatchVoidError → _void_match + _refund_credits 후 반환.
        ForfeitError → ForfeitHandler.handle_retry_exhaustion 후 반환.
        정상 완료 → DebateJudge.judge → MatchFinalizer.finalize.

        Args:
            client: 공유 InferenceClient (커넥션 풀 재사용).
            match: 실행 중인 매치.
            topic: 토론 주제.
            agent_a: A측 에이전트.
            agent_b: B측 에이전트.
            version_a: A측 에이전트 버전 스냅샷. 없으면 기본 프롬프트 사용.
            version_b: B측 에이전트 버전 스냅샷. 없으면 기본 프롬프트 사용.
            api_key_a: A측 LLM API 키.
            api_key_b: B측 LLM API 키.
        """
        orchestrator = DebateOrchestrator(optimized=settings.debate_orchestrator_optimized, client=client)
        judge_instance = DebateJudge(client=client)
        executor = TurnExecutor(client, self.db)
        model_cache: dict[str, LLMModel] = {}
        usage_batch: list[TokenUsageLog] = []

        match_format = getattr(match, "format", "1v1")
        if match_format not in ("1v1", "multi"):
            raise MatchVoidError(f"Unknown format: {match_format}")
        runner = get_format_runner(match_format)

        intro = await judge_instance.generate_intro(
            topic,
            agent_a_name=agent_a.name,
            agent_b_name=agent_b.name,
            trace_id=str(match.id),
            orchestration_mode=match_format,
        )
        try:
            await publish_event(str(match.id), "judge_intro", {
                "message": intro.get("message"),
                "topic_title": topic.title,
                "model_id": intro.get("model_id"),
                "input_tokens": intro.get("input_tokens", 0),
                "output_tokens": intro.get("output_tokens", 0),
                "fallback_reason": intro.get("fallback_reason"),
            })
        except Exception:
            # judge_intro 발행 실패는 비치명적 — intro 없이 토론 진행, 크레딧 미환불 경로 차단
            logger.warning("judge_intro publish failed for match %s — continuing", match.id)
        intro_message = (intro.get("message") or "").strip()
        if intro_message:
            # 턴 루프 컨텍스트에서만 judge_intro를 별도 섹션으로 주입한다.
            turn_topic = SimpleNamespace(
                title=topic.title,
                description=topic.description,
                max_turns=topic.max_turns,
                turn_token_limit=topic.turn_token_limit,
                tools_enabled=topic.tools_enabled,
                judge_intro=intro_message,
            )
        else:
            turn_topic = topic

        try:
            if match_format == "1v1":
                loop_result: TurnLoopResult = await runner(
                    executor, orchestrator, self.db, match, turn_topic,
                    agent_a, agent_b, version_a, version_b, api_key_a, api_key_b,
                    model_cache, usage_batch,
                    parallel=orchestrator.optimized,
                )
            else:
                loop_result = await runner(
                    executor, orchestrator, self.db, match, turn_topic,
                    agent_a, agent_b, model_cache, usage_batch,
                )
        except MatchVoidError as void_err:
            await self._void_match(match, str(void_err))
            await self._refund_credits(match)
            return
        except ForfeitError as forfeit:
            await ForfeitHandler(self.db).handle_retry_exhaustion(match, agent_a, agent_b, forfeit.forfeited_speaker)
            await self._refund_credits(match)
            return

        match.penalty_a = loop_result.total_penalty_a
        match.penalty_b = loop_result.total_penalty_b
        await self.db.commit()

        turns_res = await self.db.execute(
            select(DebateTurnLog)
            .where(DebateTurnLog.match_id == match.id)
            .order_by(DebateTurnLog.turn_number, DebateTurnLog.speaker)
        )
        turns = list(turns_res.scalars().all())
        try:
            judgment = await judge_instance.judge(
                match, turns, topic, agent_a_name=agent_a.name, agent_b_name=agent_b.name
            )
        except Exception as judge_exc:
            logger.error("Judge failed for match %s: %s — voiding match", match.id, judge_exc, exc_info=True)
            await self._void_match(match, f"judge_failed: {judge_exc}")
            await self._refund_credits(match)
            return

        finalizer = MatchFinalizer(self.db)
        try:
            await finalizer.finalize(
                match,
                judgment,
                agent_a,
                agent_b,
                loop_result.model_cache,
                loop_result.usage_batch,
            )
        except Exception as fin_exc:
            logger.error("finalize failed for match %s: %s — voiding", match.id, fin_exc, exc_info=True)
            await self._void_match(match, f"finalize_failed: {fin_exc}")
            await self._refund_credits(match)
            return


# ── 매치 실행 진입점 ──────────────────────────────────────────────────────────


async def _mark_error_in_db(match_id: str) -> None:
    """매치 상태를 error로 마킹한다. 독립 세션 사용 — 공유 세션 오염 없음."""
    async with async_session() as db:
        try:
            await db.execute(
                update(DebateMatch)
                .where(DebateMatch.id == match_id)
                .values(status="error", finished_at=datetime.now(UTC))
            )
            await db.commit()
        except Exception:
            logger.error("Failed to mark match %s as error in DB", match_id, exc_info=True)


async def run_debate(match_id: str) -> None:
    """매치 실행 진입점. app-level DB 세션 풀로 백그라운드 태스크에서 호출된다.

    DebateEngine.run() 래핑 후 예외별 처리:
      - CreditInsufficientError: credit_insufficient SSE 이미 발행됨 — error SSE 추가 알림
      - CancelledError: 독립 세션(_mark_error_in_db)으로 DB 마킹 후 재발생
      - Exception: DB error 마킹 + error SSE 발행

    Args:
        match_id: 실행할 매치 UUID 문자열.
    """
    # 순환 import 방지를 위해 함수 레벨 import — 한 번만 선언
    from app.services.notification_service import NotificationService

    async with async_session() as notify_db:
        try:
            await NotificationService(notify_db).notify_match_event(match_id, "match_started")
            await notify_db.commit()
        except Exception:
            logger.warning("Start notification failed for match %s", match_id, exc_info=True)

    async with async_session() as db:
        try:
            engine = DebateEngine(db)
            await engine.run(match_id)
        except CreditInsufficientError as exc:
            logger.warning("Match %s aborted: %s", match_id, exc)
            await _mark_error_in_db(match_id)
            # credit_insufficient 이후 error 이벤트로 프론트에 매치 종료 명시적으로 알림
            try:
                await publish_event(match_id, "error", {"message": str(exc), "error_type": "credit_insufficient"})
            except Exception:
                logger.warning("Failed to publish error event after credit failure for match %s", match_id)
        except asyncio.CancelledError:
            logger.warning("Debate task cancelled for match %s — marking as error", match_id)
            try:
                # 독립 세션 사용 — 공유 db 세션 종료 후에도 안전하게 DB 마킹 완료
                await asyncio.shield(_mark_error_in_db(match_id))
            except Exception as cleanup_exc:
                logger.error("Cleanup failed for cancelled match %s: %s", match_id, cleanup_exc)
            try:
                await publish_event(match_id, "error", {"message": "Match cancelled by server"})
            except Exception:
                logger.warning("Failed to publish cancel SSE for match %s", match_id)
            raise
        except Exception as exc:
            logger.error("Debate engine error for match %s: %s", match_id, exc, exc_info=True)
            await _mark_error_in_db(match_id)
            # DB 마킹 성공 여부와 무관하게 SSE 발행 시도 — 실패해도 태스크 종료에 영향 없도록
            try:
                await publish_event(match_id, "error", {"message": str(exc)})
            except Exception:
                logger.warning("Failed to publish error event for match %s", match_id)
        else:
            async with async_session() as notify_db:
                try:
                    result = await notify_db.execute(
                        select(DebateMatch).where(DebateMatch.id == match_id)
                    )
                    m = result.scalar_one_or_none()
                    # forfeit/void/error로 종료된 매치는 match_finished 미발송
                    if m and m.status == "finished":
                        await NotificationService(notify_db).notify_match_event(match_id, "match_finished")
                        await notify_db.commit()
                except Exception:
                    logger.warning("Finish notification failed for match %s", match_id, exc_info=True)
