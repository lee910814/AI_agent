"""토론 포맷별 턴 루프 함수 + 포맷 dispatch."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from app.services.debate.broadcast import publish_event
from app.services.debate.forfeit import ForfeitError
from app.services.debate.helpers import _resolve_api_key
from app.services.debate.orchestrator import DebateOrchestrator
from app.services.debate.turn_executor import TurnExecutor

_TOOL_USE_PROVIDERS = frozenset({"openai", "anthropic", "google"})

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.debate.control_plane import OrchestrationControlPlane


@dataclass
class TurnLoopResult:
    """턴 루프 종료 후 DebateEngine에 반환하는 집계 결과.

    Attributes:
        claims_a: A측 발언 목록 (차단된 경우 blocked_claim 텍스트로 대체됨).
        claims_b: B측 발언 목록 (차단된 경우 blocked_claim 텍스트로 대체됨).
        total_penalty_a: A측 누적 벌점 합계.
        total_penalty_b: B측 누적 벌점 합계.
        model_cache: LLMModel 캐시 (model_id → LLMModel). finalizer에 전달.
        usage_batch: 커밋 전 모아둔 TokenUsageLog 목록. finalizer에서 일괄 INSERT.
    """

    claims_a: list[str]
    claims_b: list[str]
    total_penalty_a: int
    total_penalty_b: int
    model_cache: dict = field(default_factory=dict)
    usage_batch: list = field(default_factory=list)


# ── 이벤트 발행 헬퍼 ──────────────────────────────────────────────────────────

async def _publish_turn_event(
    match_id: str,
    turn: DebateTurnLog,
    review_result=None,
    event_meta: dict | None = None,
) -> None:
    """턴 완료 SSE 이벤트를 발행한다.

    Args:
        match_id: 이벤트를 발행할 매치 UUID 문자열.
        turn: 완료된 턴 로그 (DB 플러시 완료 상태).
        review_result: LLM 검토 결과 dict. None이면 review_result 필드를 null로 발행.
    """
    payload = {
        "turn_number": turn.turn_number,
        "speaker": turn.speaker,
        "action": turn.action,
        "claim": turn.claim,
        "evidence": turn.evidence,
        "penalties": turn.penalties,
        "penalty_total": turn.penalty_total,
        "response_time_ms": turn.response_time_ms,
        "input_tokens": turn.input_tokens,
        "output_tokens": turn.output_tokens,
        "is_blocked": turn.is_blocked,
        "tool_used": turn.tool_used,
        "review_result": review_result,
    }
    if event_meta:
        payload.update(event_meta)
    await publish_event(match_id, "turn", payload)


async def _publish_review_event(
    match_id: str,
    turn_number: int,
    speaker: str,
    review: dict,
    event_meta: dict | None = None,
    fallback_reason: str | None = None,
) -> None:
    """리뷰 결과 SSE 이벤트를 발행한다.

    Args:
        match_id: 이벤트를 발행할 매치 UUID 문자열.
        turn_number: 리뷰 대상 턴 번호.
        speaker: 발언자 ('agent_a' | 'agent_b' | 슬롯 레이블).
        review: DebateOrchestrator.review_turn()이 반환한 결과 dict.
    """
    payload = {
        "turn_number": turn_number,
        "speaker": speaker,
        "logic_score": review["logic_score"],
        "violations": review["violations"],
        "feedback": review["feedback"],
        "blocked": review["block"],
    }
    if fallback_reason:
        payload["fallback_reason"] = fallback_reason
    if event_meta:
        payload.update(event_meta)
    await publish_event(match_id, "turn_review", payload)


# ── 리뷰 결과 반영 헬퍼 ───────────────────────────────────────────────────────

def _apply_review_to_turn(
    turn: DebateTurnLog,
    review: dict,
    claims: list[str],
    penalty_total: int,
    update_last_claim: bool = False,
) -> int:
    """리뷰 결과를 TurnLog에 반영하고 누적 벌점을 반환.

    update_last_claim=True: 이미 append된 claims[-1]을 차단본으로 패치 (최적화 모드용)
    update_last_claim=False: claims에 직접 append (순차 모드용, 차단 시 blocked_claim append)
    """
    for vtype, vpenalty in review["penalties"].items():
        llm_key = f"llm_{vtype}"
        if turn.penalties is None:
            turn.penalties = {}
        turn.penalties[llm_key] = vpenalty
        turn.penalty_total += vpenalty
        penalty_total += vpenalty

    # block=True: 원문 대신 blocked_claim 텍스트로 교체
    if review["block"]:
        blocked = review["blocked_claim"]
        # parallel 모드: 이미 claims에 원본이 append됐으므로 마지막 항목을 패치
        if update_last_claim and claims:
            claims[-1] = blocked
        elif not update_last_claim:
            # sequential 모드: 차단 발언도 인덱스 보존을 위해 blocked_claim 텍스트로 추가
            # (누락 시 다음 턴의 opponent_last_claim 인덱스가 어긋남)
            claims.append(blocked)
        turn.is_blocked = True
        turn.claim = blocked
    elif not update_last_claim:
        # sequential 모드: 차단되지 않은 경우에만 원본 발언을 claims에 추가
        claims.append(turn.claim)

    turn.review_result = {
        "logic_score": review["logic_score"],
        "violations": review["violations"],
        "feedback": review["feedback"],
        "blocked": review["block"],
        "skipped": review.get("skipped", False),
    }
    return penalty_total


# ── 오케스트레이터 토큰 기록 헬퍼 ────────────────────────────────────────────

async def _log_orchestrator_usage(
    db: AsyncSession,
    user_id: uuid.UUID,
    model_str: str,
    input_tokens: int,
    output_tokens: int,
    model_cache: dict | None = None,
    usage_batch: list | None = None,
    match_id: uuid.UUID | None = None,
) -> None:
    """오케스트레이터 LLM 호출 토큰을 token_usage_logs에 기록한다.

    input_tokens == output_tokens == 0이면 즉시 반환 (폴백/스킵된 호출).
    model_cache를 활용해 동일 모델 반복 DB 조회를 방지한다.
    usage_batch가 None이면 즉시 db.add(), 있으면 배치에 추가 (매치 종료 시 일괄 INSERT).

    Args:
        db: 비동기 DB 세션.
        user_id: 사용량을 기록할 사용자 UUID.
        model_str: LLM 모델 ID 문자열 (llm_models.model_id).
        input_tokens: 입력 토큰 수.
        output_tokens: 출력 토큰 수.
        model_cache: model_id → LLMModel 캐시 dict. None이면 매번 DB 조회.
        usage_batch: 배치 INSERT용 TokenUsageLog 목록. None이면 즉시 INSERT.
        match_id: 연관된 토론 매치 UUID. None이면 매치 외 호출.
    """
    if input_tokens == 0 and output_tokens == 0:
        return

    # 캐시 우선 조회 — 매 호출마다 DB SELECT 방지
    if model_cache is not None and model_str in model_cache:
        model = model_cache[model_str]
    else:
        result = await db.execute(
            select(LLMModel).where(LLMModel.model_id == model_str)
        )
        model = result.scalar_one_or_none()
        if model_cache is not None and model is not None:
            model_cache[model_str] = model

    if model is None:
        logger.warning("_log_orchestrator_usage: model_id=%s not found in llm_models", model_str)
        return
    from app.services.debate.match_service import calculate_token_cost
    input_cost = calculate_token_cost(input_tokens, model.input_cost_per_1m)
    output_cost = calculate_token_cost(output_tokens, model.output_cost_per_1m)
    log = TokenUsageLog(
        user_id=user_id,
        session_id=None,
        match_id=match_id,
        llm_model_id=model.id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=input_cost + output_cost,
    )
    if usage_batch is not None:
        # 배치 모드: 매치 종료 시 일괄 INSERT
        usage_batch.append(log)
    else:
        db.add(log)


# ── 포맷 dispatch ──────────────────────────────────────────────────────────────


def get_format_runner(match_format: str) -> Callable:
    """매치 포맷에 대응하는 턴 루프 함수를 반환한다.

    lazy import로 순환 참조를 방지한다.
    등록되지 않은 포맷은 run_turns_1v1로 폴백한다.

    Args:
        match_format: 매치 포맷 문자열 ('1v1' | '2v2' | '3v3').

    Returns:
        대응하는 턴 루프 코루틴 함수.
    """
    from app.services.debate.format_1v1 import run_turns_1v1
    from app.services.debate.format_multi import run_turns_multi

    _runners: dict[str, Callable] = {
        "1v1": run_turns_1v1,
        "2v2": run_turns_multi,
        "3v3": run_turns_multi,
    }
    return _runners.get(match_format, run_turns_1v1)
