"""멀티에이전트 포맷 턴 루프 함수 모음."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.services.debate.forfeit import ForfeitError
from app.services.debate.helpers import _resolve_api_key
from app.services.debate.orchestrator import DebateOrchestrator
from app.services.debate.turn_executor import TurnExecutor
from app.services.debate.debate_formats import (
    TurnLoopResult,
    _TOOL_USE_PROVIDERS,
    _apply_review_to_turn,
    _log_orchestrator_usage,
    _publish_review_event,
    _publish_turn_event,
)
from app.services.debate.format_1v1 import (
    _has_severe_violation,
    _update_accumulated_violations,
)
from app.services.debate.broadcast import publish_event

if TYPE_CHECKING:
    from app.services.debate.control_plane import OrchestrationControlPlane

logger = logging.getLogger(__name__)


async def _run_multi_slot_turn(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    turn_num: int,
    speaker_role: str,
    speaker_label: str,
    agent: DebateAgent,
    version: DebateAgentVersion | None,
    api_key: str,
    my_claims: list[str],
    opp_claims: list[str],
    total_penalty: int,
    model_cache: dict,
    usage_batch: list,
    control_plane: "OrchestrationControlPlane | None" = None,
    accumulated_violations: dict[str, int] | None = None,
) -> tuple[int, dict | None]:
    """멀티에이전트 슬롯 단일 턴: 실행 → 검토 → 이벤트 발행.

    agent_a/b 처리 블록의 중복 제거를 위해 추출. run_turns_multi() 루프 내에서
    speaker_role("agent_a"|"agent_b")과 speaker_label("agent_a_slot0" 등)을 분리해
    1v1과 동일한 이벤트 형식으로 발행한다.

    Returns:
        (total_penalty, review_result) — review_result는 LLM 검토 비활성 시 None.
    """
    turn = await executor.execute_with_retry(
        match, topic, turn_num, speaker_role,
        agent, version, api_key, my_claims, opp_claims,
        my_accumulated_penalty=total_penalty,
        event_meta=control_plane.event_meta(turn_number=turn_num, speaker=speaker_label) if control_plane else None,
    )
    if turn is None:
        raise ForfeitError(forfeited_speaker=speaker_role)
    total_penalty += turn.penalty_total

    if settings.debate_turn_review_enabled:
        review = await orchestrator.review_turn(
            topic=topic.title,
            speaker=speaker_label,
            turn_number=turn_num,
            claim=turn.claim,
            evidence=turn.evidence,
            action=turn.action,
            opponent_last_claim=opp_claims[-1] if opp_claims else None,
            recent_history=my_claims[-2:] if my_claims else None,
            trace_id=control_plane.runtime.trace_id if control_plane else None,
            orchestration_mode=control_plane.runtime.mode if control_plane else None,
            tools_available=(
                settings.debate_tool_use_enabled and topic.tools_enabled and agent.provider in _TOOL_USE_PROVIDERS
            ),
            tool_result=(turn.raw_response or {}).get("tool_raw_content") or (turn.raw_response or {}).get("tool_result"),
            debater_position=speaker_role.replace("agent_", "").upper() + " 측",
            opponent_recent_history=opp_claims[-2:] if opp_claims else None,
            max_turns=topic.max_turns,
            accumulated_violations=accumulated_violations,
        )
        total_penalty = _apply_review_to_turn(
            turn, review, my_claims, total_penalty, update_last_claim=False
        )
        await _log_orchestrator_usage(
            db, agent.owner_id, review.get("model_id", ""),
            review["input_tokens"], review["output_tokens"],
            model_cache=model_cache, usage_batch=usage_batch,
            match_id=match.id,
        )
        fallback_reason = review.get("fallback_reason")
        if control_plane and fallback_reason:
            control_plane.mark_fallback(
                fallback_reason,
                stage="review",
                turn_number=turn_num,
                speaker=speaker_label,
            )
        await _publish_review_event(
            str(match.id),
            turn_num,
            speaker_label,
            review,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker=speaker_label, fallback_reason=fallback_reason)
            if control_plane else None,
            fallback_reason=fallback_reason,
        )
        review_returned = review
    else:
        my_claims.append(turn.claim)
        review_returned = None

    # turn.speaker는 "agent_a"|"agent_b"이므로 슬롯 레이블로 오버라이드
    await _publish_turn_event(
        str(match.id),
        turn,
        turn.review_result,
        event_meta=control_plane.event_meta(turn_number=turn_num, speaker=speaker_label) if control_plane else None,
    )
    # 슬롯 레이블을 별도 필드로 보완 (프론트엔드 멀티에이전트 구분용)
    slot_payload = {"speaker": speaker_label, "turn_number": turn_num}
    if control_plane:
        slot_payload.update(control_plane.event_meta(turn_number=turn_num, speaker=speaker_label))
    await publish_event(str(match.id), "turn_slot", slot_payload)

    return total_penalty, review_returned


async def run_turns_multi(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    model_cache: dict,
    usage_batch: list,
    control_plane: "OrchestrationControlPlane | None" = None,
) -> TurnLoopResult:
    """멀티에이전트 턴 루프 (2v2/3v3 라운드 로빈).

    DebateMatchParticipant를 team A/B로 분류한 뒤 슬롯 인덱스를 라운드 로빈으로 순환.
    슬롯 수가 팀 간 다를 경우 짧은 팀은 mod 연산으로 순환 재사용된다.
    에이전트·버전은 루프 진입 전 한 번에 배치 조회해 반복 DB SELECT를 방지한다.

    Args:
        executor: 단일 턴 실행기.
        orchestrator: LLM 검토 오케스트레이터.
        db: 비동기 DB 세션.
        match: 실행 중인 멀티에이전트 매치.
        topic: 토론 주제.
        agent_a: 대표 A측 에이전트 (ELO·판정용, 실제 발언은 participants 기반).
        agent_b: 대표 B측 에이전트 (ELO·판정용, 실제 발언은 participants 기반).
        model_cache: LLMModel 캐시 dict.
        usage_batch: 배치 INSERT용 TokenUsageLog 목록.

    Returns:
        TurnLoopResult: 발언 목록·누적 벌점·캐시 등 턴 루프 집계 결과.

    Raises:
        ForfeitError: 슬롯 에이전트 발언이 모든 재시도 후에도 실패한 경우.
    """
    from app.models.debate_match import DebateMatchParticipant

    parts_res = await db.execute(
        select(DebateMatchParticipant)
        .where(DebateMatchParticipant.match_id == match.id)
        .order_by(DebateMatchParticipant.team, DebateMatchParticipant.slot)
    )
    parts = list(parts_res.scalars().all())
    team_a = [p for p in parts if p.team == "A"]
    team_b = [p for p in parts if p.team == "B"]

    if not team_a or not team_b:
        logger.warning("Multi-agent match %s has no participants, skipping", match.id)
        return TurnLoopResult([], [], 0, 0, model_cache, usage_batch)

    max_slots = max(len(team_a), len(team_b))

    # 루프 진입 전 에이전트/버전을 한 번에 배치 조회
    from app.models.debate_agent import DebateAgentVersion as AgentVersion
    all_agent_ids = list({p.agent_id for p in parts if p.agent_id is not None})
    agents_res = await db.execute(
        select(DebateAgent).where(DebateAgent.id.in_(all_agent_ids))
    )
    agents_cache: dict = {str(a.id): a for a in agents_res.scalars().all()}

    all_version_ids = list({p.version_id for p in parts if p.version_id is not None})
    versions_cache: dict = {}
    if all_version_ids:
        versions_res = await db.execute(
            select(AgentVersion).where(AgentVersion.id.in_(all_version_ids))
        )
        versions_cache = {str(v.id): v for v in versions_res.scalars().all()}

    claims_a: list[str] = []
    claims_b: list[str] = []
    total_penalty_a = 0
    total_penalty_b = 0
    accumulated_violations_a: dict[str, int] = {}
    accumulated_violations_b: dict[str, int] = {}
    consecutive_severe_a = 0
    consecutive_severe_b = 0

    for turn_num in range(1, topic.max_turns + 1):
        for i in range(max_slots):
            a_part = team_a[i % len(team_a)]
            b_part = team_b[i % len(team_b)]

            multi_agent_a = agents_cache.get(str(a_part.agent_id))
            multi_agent_b = agents_cache.get(str(b_part.agent_id))

            if multi_agent_a is None or multi_agent_b is None:
                # opp_claims 인덱스 정합성 유지 — None placeholder로 슬롯 공백 표시
                # `opp_claims[-1] if opp_claims else None` 가드와 호환
                logger.warning(
                    "Multi-agent: agent not found, slot %d turn %d — inserting None placeholder", i, turn_num
                )
                if multi_agent_a is None:
                    claims_a.append(None)
                if multi_agent_b is None:
                    claims_b.append(None)
                continue

            api_key_a = _resolve_api_key(multi_agent_a)
            api_key_b = _resolve_api_key(multi_agent_b)

            ver_a = versions_cache.get(str(a_part.version_id)) if a_part.version_id else None
            ver_b = versions_cache.get(str(b_part.version_id)) if b_part.version_id else None

            total_penalty_a, review_a = await _run_multi_slot_turn(
                executor, orchestrator, db, match, topic, turn_num,
                "agent_a", f"agent_a_slot{i}",
                multi_agent_a, ver_a, api_key_a, claims_a, claims_b,
                total_penalty_a, model_cache, usage_batch, control_plane=control_plane,
                accumulated_violations=accumulated_violations_a,
            )
            if review_a is not None:
                if _has_severe_violation(review_a):
                    consecutive_severe_a += 1
                else:
                    consecutive_severe_a = 0
                _update_accumulated_violations(accumulated_violations_a, review_a)
                _streak = settings.debate_forfeit_on_severe_streak
                if _streak and consecutive_severe_a >= _streak:
                    raise ForfeitError(forfeited_speaker="agent_a")

            total_penalty_b, review_b = await _run_multi_slot_turn(
                executor, orchestrator, db, match, topic, turn_num,
                "agent_b", f"agent_b_slot{i}",
                multi_agent_b, ver_b, api_key_b, claims_b, claims_a,
                total_penalty_b, model_cache, usage_batch, control_plane=control_plane,
                accumulated_violations=accumulated_violations_b,
            )
            if review_b is not None:
                if _has_severe_violation(review_b):
                    consecutive_severe_b += 1
                else:
                    consecutive_severe_b = 0
                _update_accumulated_violations(accumulated_violations_b, review_b)
                _streak = settings.debate_forfeit_on_severe_streak
                if _streak and consecutive_severe_b >= _streak:
                    raise ForfeitError(forfeited_speaker="agent_b")

    return TurnLoopResult(claims_a, claims_b, total_penalty_a, total_penalty_b, model_cache, usage_batch)
