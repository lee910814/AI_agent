"""1v1 포맷 턴 루프 함수 모음."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.services.debate.broadcast import publish_event
from app.services.debate.evidence_search import EvidenceResult, EvidenceSearchService
from app.services.debate.forfeit import ForfeitError
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

if TYPE_CHECKING:
    from app.services.debate.control_plane import OrchestrationControlPlane

_evidence_service = EvidenceSearchService()
logger = logging.getLogger(__name__)


def _has_severe_violation(review: dict) -> bool:
    """review dict에 severity=severe인 위반이 하나 이상 있으면 True."""
    return any(v.get("severity") == "severe" for v in review.get("violations", []))


def _update_accumulated_violations(accumulated: dict[str, int], review: dict) -> None:
    """review의 violations를 accumulated 딕셔너리에 카운트 누적한다."""
    for v in review.get("violations", []):
        vtype = v.get("type", "")
        if vtype:
            accumulated[vtype] = accumulated.get(vtype, 0) + 1


async def run_turns_1v1(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    version_a: DebateAgentVersion | None,
    version_b: DebateAgentVersion | None,
    api_key_a: str,
    api_key_b: str,
    model_cache: dict,
    usage_batch: list,
    parallel: bool,
    control_plane: "OrchestrationControlPlane | None" = None,
) -> TurnLoopResult:
    """1v1 포맷 턴 루프 진입점.

    parallel=True이면 롤링 create_task 병렬 패턴(_run_parallel_turns)을 사용하고,
    parallel=False이면 순차 패턴(_run_sequential_turns)을 사용한다.
    에이전트 발언이 재시도를 모두 소진하면 ForfeitError를 raise한다.

    Args:
        executor: 단일 턴 실행기.
        orchestrator: LLM 검토 오케스트레이터.
        db: 비동기 DB 세션.
        match: 실행 중인 매치.
        topic: 토론 주제.
        agent_a: A측 에이전트.
        agent_b: B측 에이전트.
        version_a: A측 에이전트 버전 스냅샷.
        version_b: B측 에이전트 버전 스냅샷.
        api_key_a: A측 LLM API 키.
        api_key_b: B측 LLM API 키.
        model_cache: LLMModel 캐시 dict (호출 간 공유).
        usage_batch: 배치 INSERT용 TokenUsageLog 목록.
        parallel: True면 병렬 패턴, False면 순차 패턴 사용.

    Returns:
        TurnLoopResult: 발언 목록·누적 벌점·캐시 등 턴 루프 집계 결과.

    Raises:
        ForfeitError: 에이전트 발언이 모든 재시도 후에도 실패한 경우.
    """
    claims_a: list[str] = []
    claims_b: list[str] = []

    if parallel:
        total_penalty_a, total_penalty_b = await _run_parallel_turns(
            executor, orchestrator, db, match, topic,
            agent_a, agent_b, version_a, version_b, api_key_a, api_key_b,
            claims_a, claims_b, model_cache, usage_batch, control_plane=control_plane,
        )
    else:
        total_penalty_a, total_penalty_b = await _run_sequential_turns(
            executor, orchestrator, db, match, topic,
            agent_a, agent_b, version_a, version_b, api_key_a, api_key_b,
            claims_a, claims_b, model_cache, usage_batch, control_plane=control_plane,
        )

    return TurnLoopResult(claims_a, claims_b, total_penalty_a, total_penalty_b, model_cache, usage_batch)


async def _run_parallel_turns(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    version_a: DebateAgentVersion | None,
    version_b: DebateAgentVersion | None,
    api_key_a: str,
    api_key_b: str,
    claims_a: list[str],
    claims_b: list[str],
    model_cache: dict,
    usage_batch: list,
    control_plane: "OrchestrationControlPlane | None" = None,
) -> tuple[int, int]:
    """롤링 병렬 패턴 턴 루프.

    매 턴마다 A 검토와 B 실행을 asyncio.create_task로 병렬화한다.
    이전 턴의 B 리뷰 결과는 다음 턴 A 실행 직전에 수집하는 '롤링' 방식으로
    검토 대기시간을 B 실행 시간에 숨긴다 (전체 지연 약 37% 단축).

    Args:
        executor: 단일 턴 실행기.
        orchestrator: LLM 검토 오케스트레이터.
        db: 비동기 DB 세션.
        match: 실행 중인 매치.
        topic: 토론 주제.
        agent_a: A측 에이전트.
        agent_b: B측 에이전트.
        version_a: A측 에이전트 버전 스냅샷.
        version_b: B측 에이전트 버전 스냅샷.
        api_key_a: A측 LLM API 키.
        api_key_b: B측 LLM API 키.
        claims_a: A측 발언 누적 목록 (in-out 참조).
        claims_b: B측 발언 누적 목록 (in-out 참조).
        model_cache: LLMModel 캐시 dict.
        usage_batch: 배치 INSERT용 TokenUsageLog 목록.

    Returns:
        (total_penalty_a, total_penalty_b) 누적 벌점 튜플.

    Raises:
        ForfeitError: A 또는 B 발언이 모든 재시도 후에도 실패한 경우.
    """
    total_penalty_a = 0
    total_penalty_b = 0

    # settings가 MagicMock인 테스트 환경에서는 evidence task를 생성하지 않도록 엄밀 타입 검사
    # bool 타입인 경우만 True로 간주 — MagicMock은 bool이 아니므로 False로 처리됨
    _ev_enabled = isinstance(
        getattr(settings, "debate_evidence_search_enabled", False), bool
    ) and settings.debate_evidence_search_enabled

    # 매치 단위 사용 출처 추적 — 동일 URL이 여러 턴에서 반복 인용되지 않도록
    used_sources: set[str] = set()

    prev_b_review_task: asyncio.Task | None = None
    prev_b_evidence_task: asyncio.Task | None = None
    prev_turn_b = None
    prev_b_turn_num: int = 0
    # 이전 턴 evidence를 다음 턴 시스템 프롬프트에 주입 — 연속 논거 구성 지원
    prev_evidence_a: str | None = None
    prev_evidence_b: str | None = None
    consecutive_severe_a = 0
    consecutive_severe_b = 0
    accumulated_violations_a: dict[str, int] = {}
    accumulated_violations_b: dict[str, int] = {}

    for turn_num in range(1, topic.max_turns + 1):
        # ★ 롤링 병렬: 이전 턴의 B 리뷰 + 근거 검색 결과를 A 실행 시작 전에 수집
        if settings.debate_turn_review_enabled and prev_b_review_task is not None:
            try:
                review_prev_b = await prev_b_review_task
            except Exception as exc:
                logger.error("B review task failed: %s — using fallback", exc)
                review_prev_b = orchestrator.review_fallback()
            prev_b_review_task = None

            # B evidence 수집 (review와 함께 이미 대부분 완료됨)
            if prev_b_evidence_task is not None and prev_turn_b is not None:
                try:
                    evidence_b = await prev_b_evidence_task
                    raw = prev_turn_b.raw_response or {}
                    if isinstance(evidence_b, EvidenceResult) and raw.get("tool_used") != "web_search":
                        prev_turn_b.evidence = evidence_b.format()
                        used_sources.update(evidence_b.sources)
                        await db.flush()
                        await publish_event(str(match.id), "turn_evidence_patch", {
                            "turn_number": prev_b_turn_num,
                            "speaker": "agent_b",
                            "evidence": prev_turn_b.evidence,
                        })
                except Exception as exc:
                    logger.warning("B evidence task failed: %s", exc)
                prev_b_evidence_task = None
            # 이번 수집된 B evidence를 다음 턴 시스템 프롬프트에 주입하기 위해 저장
            if prev_turn_b is not None:
                prev_evidence_b = prev_turn_b.evidence

            if prev_turn_b is None:
                logger.error("prev_turn_b unexpectedly None at turn %d, skipping B review", turn_num)
                # 비정상 경로: B 발언 없이 리뷰 태스크가 생성된 경우 카운터 리셋 — 이전 severe가 누적되지 않도록
                consecutive_severe_b = 0
            else:
                total_penalty_b = _apply_review_to_turn(
                    prev_turn_b, review_prev_b, claims_b,
                    total_penalty_b, update_last_claim=True
                )
                if _has_severe_violation(review_prev_b):
                    consecutive_severe_b += 1
                else:
                    consecutive_severe_b = 0
                _update_accumulated_violations(accumulated_violations_b, review_prev_b)
                _streak = settings.debate_forfeit_on_severe_streak
                if _streak and consecutive_severe_b >= _streak:
                    if prev_b_evidence_task and not prev_b_evidence_task.done():
                        prev_b_evidence_task.cancel()
                    raise ForfeitError(forfeited_speaker="agent_b")
                await _log_orchestrator_usage(
                    db, agent_b.owner_id, review_prev_b.get("model_id", ""),
                    review_prev_b["input_tokens"], review_prev_b["output_tokens"],
                    model_cache=model_cache, usage_batch=usage_batch,
                    match_id=match.id,
                )
                fallback_reason = review_prev_b.get("fallback_reason")
                if control_plane and fallback_reason:
                    control_plane.mark_fallback(
                        fallback_reason,
                        stage="review",
                        turn_number=prev_b_turn_num,
                        speaker="agent_b",
                    )
                await _publish_review_event(
                    str(match.id),
                    prev_b_turn_num,
                    "agent_b",
                    review_prev_b,
                    event_meta=control_plane.event_meta(
                        turn_number=prev_b_turn_num,
                        speaker="agent_b",
                        fallback_reason=fallback_reason,
                    ) if control_plane else None,
                    fallback_reason=fallback_reason,
                )

        # Agent A 턴
        turn_a = await executor.execute_with_retry(
            match, topic, turn_num, "agent_a",
            agent_a, version_a, api_key_a, claims_a, claims_b,
            my_accumulated_penalty=total_penalty_a,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a") if control_plane else None,
            prev_evidence=prev_evidence_a,
        )
        if turn_a is None:
            for _t in [prev_b_review_task, prev_b_evidence_task]:
                if _t and not _t.done():
                    _t.cancel()
            raise ForfeitError(forfeited_speaker="agent_a")
        total_penalty_a += turn_a.penalty_total

        # B가 참조할 수 있도록 A 발언을 먼저 큐에 등록 (검토 전 원본)
        # P3: recent_history를 append 전에 캡처 — 현재 발언이 이전 발언 목록에 섞이지 않도록
        recent_history_a = claims_a[-2:] if claims_a else None
        claims_a.append(turn_a.claim)

        # ★ gather 전에 A turn 이벤트 먼저 발행 — B 스트리밍이 pendingStreamingTurn
        # 없이 바로 streamingTurn으로 표시되도록 순서 보장.
        await _publish_turn_event(
            str(match.id),
            turn_a,
            review_result=None,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a") if control_plane else None,
        )

        if settings.debate_turn_review_enabled:
            # A 검토를 백그라운드 태스크로 시작 — B 실행과 병렬로 진행
            review_a_task = asyncio.create_task(
                orchestrator.review_turn(
                    topic=topic.title,
                    speaker="agent_a",
                    turn_number=turn_num,
                    claim=turn_a.claim,
                    evidence=turn_a.evidence,
                    action=turn_a.action,
                    opponent_last_claim=claims_b[-1] if claims_b else None,
                    recent_history=recent_history_a,
                    trace_id=control_plane.runtime.trace_id if control_plane else None,
                    orchestration_mode=control_plane.runtime.mode if control_plane else None,
                    tools_available=(
                        settings.debate_tool_use_enabled
                        and topic.tools_enabled
                        and agent_a.provider in _TOOL_USE_PROVIDERS
                    ),
                    tool_result=(turn_a.raw_response or {}).get("tool_raw_content") or (turn_a.raw_response or {}).get("tool_result"),
                    debater_position="A (찬성)",
                    opponent_recent_history=claims_b[-2:] if claims_b else None,
                    max_turns=topic.max_turns,
                    accumulated_violations=accumulated_violations_a,
                )
            )
            # A 근거 검색도 백그라운드 시작 — B 실행 시간에 숨김
            # tool_used=web_search인 경우 이미 검색 결과가 있으므로 사후 evidence 검색 스킵
            evidence_a_task: asyncio.Task | None = asyncio.create_task(
                _evidence_service.search(turn_a.claim, exclude_urls=set(used_sources))
            ) if (_ev_enabled and turn_a.claim and (turn_a.raw_response or {}).get("tool_used") != "web_search") else None

            # B 실행 (A 검토와 병렬)
            turn_b = await executor.execute_with_retry(
                match, topic, turn_num, "agent_b",
                agent_b, version_b, api_key_b, claims_b, claims_a,
                my_accumulated_penalty=total_penalty_b,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
                prev_evidence=prev_evidence_b,
            )
            if turn_b is None:
                # P1: turn_b 실패 시 현재 실행 중인 review_a_task와 evidence_a_task도 취소
                for _t in [review_a_task, evidence_a_task, prev_b_review_task, prev_b_evidence_task]:
                    if _t and not _t.done():
                        _t.cancel()
                raise ForfeitError(forfeited_speaker="agent_b")
            total_penalty_b += turn_b.penalty_total

            # B 발언을 검토 전에 즉시 등록 — 다음 턴 A가 원본 클레임을 참조할 수 있도록
            # P3: recent_history를 append 전에 캡처
            recent_history_b = claims_b[-2:] if claims_b else None
            claims_b.append(turn_b.claim)

            # ★ B 턴 이벤트 즉시 발행 — A 검토 완료를 기다리지 않으므로 스트리밍 지연 없음
            await _publish_turn_event(
                str(match.id),
                turn_b,
                review_result=None,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
            )

            # ★ B 리뷰를 백그라운드 태스크로 시작 — 다음 턴 A 실행과 병렬로 진행
            prev_b_review_task = asyncio.create_task(
                orchestrator.review_turn(
                    topic=topic.title,
                    speaker="agent_b",
                    turn_number=turn_num,
                    claim=turn_b.claim,
                    evidence=turn_b.evidence,
                    action=turn_b.action,
                    opponent_last_claim=claims_a[-1] if claims_a else None,
                    recent_history=recent_history_b,
                    trace_id=control_plane.runtime.trace_id if control_plane else None,
                    orchestration_mode=control_plane.runtime.mode if control_plane else None,
                    tools_available=(
                        settings.debate_tool_use_enabled
                        and topic.tools_enabled
                        and agent_b.provider in _TOOL_USE_PROVIDERS
                    ),
                    tool_result=(turn_b.raw_response or {}).get("tool_raw_content") or (turn_b.raw_response or {}).get("tool_result"),
                    debater_position="B (반대)",
                    opponent_recent_history=claims_a[-2:] if claims_a else None,
                    max_turns=topic.max_turns,
                    accumulated_violations=accumulated_violations_b,
                )
            )
            # B 근거 검색도 백그라운드 시작 — 다음 턴 A 실행 시간에 숨김
            # tool_used=web_search인 경우 이미 검색 결과가 있으므로 사후 evidence 검색 스킵
            prev_b_evidence_task = asyncio.create_task(
                _evidence_service.search(turn_b.claim, exclude_urls=set(used_sources))
            ) if (_ev_enabled and turn_b.claim and (turn_b.raw_response or {}).get("tool_used") != "web_search") else None
            prev_turn_b = turn_b
            prev_b_turn_num = turn_num

            # A 검토 + 근거 검색 완료 대기 (B 실행 동안 이미 상당 부분 진행됨)
            review_start = time.monotonic()
            try:
                review_a = await review_a_task
            except Exception as exc:
                logger.error("A review task failed: %s — using fallback", exc)
                review_a = orchestrator.review_fallback()
            if evidence_a_task is not None:
                try:
                    evidence_a = await evidence_a_task
                    raw = turn_a.raw_response or {}
                    if isinstance(evidence_a, EvidenceResult) and raw.get("tool_used") != "web_search":
                        turn_a.evidence = evidence_a.format()
                        used_sources.update(evidence_a.sources)
                        await db.flush()
                        await publish_event(str(match.id), "turn_evidence_patch", {
                            "turn_number": turn_num,
                            "speaker": "agent_a",
                            "evidence": turn_a.evidence,
                        })
                except Exception as exc:
                    logger.warning("A evidence task failed: %s", exc)
            # 이번 턴 A evidence를 다음 턴 시스템 프롬프트에 주입하기 위해 저장
            prev_evidence_a = turn_a.evidence
            evidence_a_task = None
            turn_elapsed = time.monotonic() - review_start

            # A 검토 결과 반영 (차단 시 claims_a 마지막 항목 패치)
            total_penalty_a = _apply_review_to_turn(
                turn_a, review_a, claims_a,
                total_penalty_a, update_last_claim=True
            )
            if _has_severe_violation(review_a):
                consecutive_severe_a += 1
            else:
                consecutive_severe_a = 0
            _update_accumulated_violations(accumulated_violations_a, review_a)
            _streak = settings.debate_forfeit_on_severe_streak
            if _streak and consecutive_severe_a >= _streak:
                # 진행 중인 B 리뷰·근거 태스크 취소
                for _t in [prev_b_review_task, prev_b_evidence_task]:
                    if _t and not _t.done():
                        _t.cancel()
                raise ForfeitError(forfeited_speaker="agent_a")
            await _log_orchestrator_usage(
                db, agent_a.owner_id, review_a.get("model_id", ""),
                review_a["input_tokens"], review_a["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
                match_id=match.id,
            )
            fallback_reason = review_a.get("fallback_reason")
            if control_plane and fallback_reason:
                control_plane.mark_fallback(
                    fallback_reason,
                    stage="review",
                    turn_number=turn_num,
                    speaker="agent_a",
                )
            await _publish_review_event(
                str(match.id),
                turn_num,
                "agent_a",
                review_a,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a", fallback_reason=fallback_reason)
                if control_plane else None,
                fallback_reason=fallback_reason,
            )
        else:
            # 리뷰 비활성: B 순차 실행
            b_exec_start = time.monotonic()
            turn_b = await executor.execute_with_retry(
                match, topic, turn_num, "agent_b",
                agent_b, version_b, api_key_b, claims_b, claims_a,
                my_accumulated_penalty=total_penalty_b,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
            )
            turn_elapsed = time.monotonic() - b_exec_start
            if turn_b is None:
                raise ForfeitError(forfeited_speaker="agent_b")
            total_penalty_b += turn_b.penalty_total
            claims_b.append(turn_b.claim)
            await _publish_turn_event(
                str(match.id),
                turn_b,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
            )

        # 라운드 사이 딜레이 (마지막 제외)
        if turn_num < topic.max_turns:
            remaining_delay = settings.debate_turn_delay_seconds - turn_elapsed
            if remaining_delay > 0:
                await asyncio.sleep(remaining_delay)

    # ★ 롤링 병렬: 루프 종료 후 마지막 B 리뷰·근거 수집
    # review_task를 먼저 await — LLM 호출(수백 ms) 완료 후 evidence_task도 done()일 가능성이 높아짐
    if settings.debate_turn_review_enabled and prev_b_review_task is not None:
        try:
            review_last_b = await prev_b_review_task
        except Exception as exc:
            logger.error("Last B review task failed: %s — using fallback", exc)
            review_last_b = orchestrator.review_fallback()

        if prev_turn_b is None:
            logger.error("prev_turn_b unexpectedly None after loop, skipping last B review")
        else:
            total_penalty_b = _apply_review_to_turn(
                prev_turn_b, review_last_b, claims_b,
                total_penalty_b, update_last_claim=True
            )
            if _has_severe_violation(review_last_b):
                consecutive_severe_b += 1
            else:
                consecutive_severe_b = 0
            _update_accumulated_violations(accumulated_violations_b, review_last_b)
            _streak = settings.debate_forfeit_on_severe_streak
            if _streak and consecutive_severe_b >= _streak:
                # 루프 후 마지막 B 검토에서 임계치 도달 — prev_b_evidence_task는 L722-739에서 처리되지 못하므로 직접 취소
                if prev_b_evidence_task and not prev_b_evidence_task.done():
                    prev_b_evidence_task.cancel()
                raise ForfeitError(forfeited_speaker="agent_b")
            await _log_orchestrator_usage(
                db, agent_b.owner_id, review_last_b.get("model_id", ""),
                review_last_b["input_tokens"], review_last_b["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
                match_id=match.id,
            )
            fallback_reason = review_last_b.get("fallback_reason")
            if control_plane and fallback_reason:
                control_plane.mark_fallback(
                    fallback_reason,
                    stage="review",
                    turn_number=prev_b_turn_num,
                    speaker="agent_b",
                )
            await _publish_review_event(
                str(match.id),
                prev_b_turn_num,
                "agent_b",
                review_last_b,
                event_meta=control_plane.event_meta(
                    turn_number=prev_b_turn_num,
                    speaker="agent_b",
                    fallback_reason=fallback_reason,
                ) if control_plane else None,
                fallback_reason=fallback_reason,
            )

    # review_task await 후 evidence_task 체크 — review LLM 완료 시점에 evidence도 done()일 가능성 높음
    if settings.debate_turn_review_enabled and prev_b_evidence_task is not None and prev_turn_b is not None:
        if prev_b_evidence_task.done() and not prev_b_evidence_task.cancelled():
            try:
                evidence_last_b = prev_b_evidence_task.result()
                raw = prev_turn_b.raw_response or {}
                if isinstance(evidence_last_b, EvidenceResult) and raw.get("tool_used") != "web_search":
                    prev_turn_b.evidence = evidence_last_b.format()
                    await db.flush()
                    await publish_event(str(match.id), "turn_evidence_patch", {
                        "turn_number": prev_b_turn_num,
                        "speaker": "agent_b",
                        "evidence": prev_turn_b.evidence,
                    })
            except Exception as exc:
                logger.warning("Last B evidence task failed: %s", exc)
        else:
            # 미완료 태스크 취소 — 루프 종료 후 고아 태스크로 남지 않도록
            prev_b_evidence_task.cancel()

    return total_penalty_a, total_penalty_b


async def _run_sequential_turns(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    version_a: DebateAgentVersion | None,
    version_b: DebateAgentVersion | None,
    api_key_a: str,
    api_key_b: str,
    claims_a: list[str],
    claims_b: list[str],
    model_cache: dict,
    usage_batch: list,
    control_plane: "OrchestrationControlPlane | None" = None,
) -> tuple[int, int]:
    """순차 턴 루프. DEBATE_ORCHESTRATOR_OPTIMIZED=false 시 또는 롤백 경로에서 사용.

    A 실행 → A 검토 → B 실행 → B 검토 순서로 순차 처리.
    검토 소요시간은 턴 딜레이에서 차감해 관전 UX를 보존한다.

    Args:
        executor: 단일 턴 실행기.
        orchestrator: LLM 검토 오케스트레이터.
        db: 비동기 DB 세션.
        match: 실행 중인 매치.
        topic: 토론 주제.
        agent_a: A측 에이전트.
        agent_b: B측 에이전트.
        version_a: A측 에이전트 버전 스냅샷.
        version_b: B측 에이전트 버전 스냅샷.
        api_key_a: A측 LLM API 키.
        api_key_b: B측 LLM API 키.
        claims_a: A측 발언 누적 목록 (in-out 참조).
        claims_b: B측 발언 누적 목록 (in-out 참조).
        model_cache: LLMModel 캐시 dict.
        usage_batch: 배치 INSERT용 TokenUsageLog 목록.

    Returns:
        (total_penalty_a, total_penalty_b) 누적 벌점 튜플.

    Raises:
        ForfeitError: A 또는 B 발언이 모든 재시도 후에도 실패한 경우.
    """
    total_penalty_a = 0
    total_penalty_b = 0
    prev_evidence_a: str | None = None
    prev_evidence_b: str | None = None
    consecutive_severe_a = 0
    consecutive_severe_b = 0
    accumulated_violations_a: dict[str, int] = {}
    accumulated_violations_b: dict[str, int] = {}

    for turn_num in range(1, topic.max_turns + 1):
        # Agent A 턴
        turn_a = await executor.execute_with_retry(
            match, topic, turn_num, "agent_a",
            agent_a, version_a, api_key_a, claims_a, claims_b,
            my_accumulated_penalty=total_penalty_a,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a") if control_plane else None,
            prev_evidence=prev_evidence_a,
        )
        if turn_a is None:
            raise ForfeitError(forfeited_speaker="agent_a")
        total_penalty_a += turn_a.penalty_total

        if settings.debate_turn_review_enabled:
            review_start = time.monotonic()
            review_a = await orchestrator.review_turn(
                topic=topic.title,
                speaker="agent_a",
                turn_number=turn_num,
                claim=turn_a.claim,
                evidence=turn_a.evidence,
                action=turn_a.action,
                opponent_last_claim=claims_b[-1] if claims_b else None,
                recent_history=claims_a[-2:] if claims_a else None,
                trace_id=control_plane.runtime.trace_id if control_plane else None,
                orchestration_mode=control_plane.runtime.mode if control_plane else None,
                tools_available=(
                    settings.debate_tool_use_enabled and topic.tools_enabled and agent_a.provider in _TOOL_USE_PROVIDERS
                ),
                tool_result=(turn_a.raw_response or {}).get("tool_result"),
                debater_position="A (찬성)",
                opponent_recent_history=claims_b[-2:] if claims_b else None,
                max_turns=topic.max_turns,
                accumulated_violations=accumulated_violations_a,
            )
            review_elapsed = time.monotonic() - review_start

            total_penalty_a = _apply_review_to_turn(
                turn_a, review_a, claims_a, total_penalty_a, update_last_claim=False
            )
            if _has_severe_violation(review_a):
                consecutive_severe_a += 1
            else:
                consecutive_severe_a = 0
            _update_accumulated_violations(accumulated_violations_a, review_a)
            _streak = settings.debate_forfeit_on_severe_streak
            if _streak and consecutive_severe_a >= _streak:
                raise ForfeitError(forfeited_speaker="agent_a")
            await _log_orchestrator_usage(
                db, agent_a.owner_id, review_a.get("model_id", ""),
                review_a["input_tokens"], review_a["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
                match_id=match.id,
            )
        else:
            review_a = None
            review_elapsed = 0.0
            claims_a.append(turn_a.claim)

        await _publish_turn_event(
            str(match.id),
            turn_a,
            turn_a.review_result,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a") if control_plane else None,
        )
        if review_a is not None:
            fallback_reason = review_a.get("fallback_reason")
            if control_plane and fallback_reason:
                control_plane.mark_fallback(
                    fallback_reason,
                    stage="review",
                    turn_number=turn_num,
                    speaker="agent_a",
                )
            await _publish_review_event(
                str(match.id),
                turn_num,
                "agent_a",
                review_a,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a", fallback_reason=fallback_reason)
                if control_plane else None,
                fallback_reason=fallback_reason,
            )

        # 관전 UX: 딜레이에서 검토 소요시간 차감
        remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
        if remaining_delay > 0:
            await asyncio.sleep(remaining_delay)

        # A evidence 저장 (sequential 모드에서는 review 전 evidence가 없으나, 다음 턴 주입용으로 현 값 저장)
        prev_evidence_a = turn_a.evidence

        # Agent B 턴
        turn_b = await executor.execute_with_retry(
            match, topic, turn_num, "agent_b",
            agent_b, version_b, api_key_b, claims_b, claims_a,
            my_accumulated_penalty=total_penalty_b,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
            prev_evidence=prev_evidence_b,
        )
        if turn_b is None:
            raise ForfeitError(forfeited_speaker="agent_b")
        total_penalty_b += turn_b.penalty_total

        if settings.debate_turn_review_enabled:
            review_start = time.monotonic()
            review_b = await orchestrator.review_turn(
                topic=topic.title,
                speaker="agent_b",
                turn_number=turn_num,
                claim=turn_b.claim,
                evidence=turn_b.evidence,
                action=turn_b.action,
                opponent_last_claim=claims_a[-1] if claims_a else None,
                recent_history=claims_b[-2:] if claims_b else None,
                trace_id=control_plane.runtime.trace_id if control_plane else None,
                orchestration_mode=control_plane.runtime.mode if control_plane else None,
                tools_available=(
                    settings.debate_tool_use_enabled and topic.tools_enabled and agent_b.provider in _TOOL_USE_PROVIDERS
                ),
                tool_result=(turn_b.raw_response or {}).get("tool_result"),
                debater_position="B (반대)",
                opponent_recent_history=claims_a[-2:] if claims_a else None,
                max_turns=topic.max_turns,
                accumulated_violations=accumulated_violations_b,
            )
            review_elapsed = time.monotonic() - review_start

            total_penalty_b = _apply_review_to_turn(
                turn_b, review_b, claims_b, total_penalty_b, update_last_claim=False
            )
            if _has_severe_violation(review_b):
                consecutive_severe_b += 1
            else:
                consecutive_severe_b = 0
            _update_accumulated_violations(accumulated_violations_b, review_b)
            _streak = settings.debate_forfeit_on_severe_streak
            if _streak and consecutive_severe_b >= _streak:
                raise ForfeitError(forfeited_speaker="agent_b")
            await _log_orchestrator_usage(
                db, agent_b.owner_id, review_b.get("model_id", ""),
                review_b["input_tokens"], review_b["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
                match_id=match.id,
            )
        else:
            review_b = None
            review_elapsed = 0.0
            claims_b.append(turn_b.claim)

        await _publish_turn_event(
            str(match.id),
            turn_b,
            turn_b.review_result,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
        )
        if review_b is not None:
            fallback_reason = review_b.get("fallback_reason")
            if control_plane and fallback_reason:
                control_plane.mark_fallback(
                    fallback_reason,
                    stage="review",
                    turn_number=turn_num,
                    speaker="agent_b",
                )
            await _publish_review_event(
                str(match.id),
                turn_num,
                "agent_b",
                review_b,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b", fallback_reason=fallback_reason)
                if control_plane else None,
                fallback_reason=fallback_reason,
            )

        # B evidence 저장 — 다음 턴 B 시스템 프롬프트 주입용
        prev_evidence_b = turn_b.evidence

        # 라운드 사이 딜레이 (마지막 제외)
        if turn_num < topic.max_turns:
            remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
            if remaining_delay > 0:
                await asyncio.sleep(remaining_delay)

    return total_penalty_a, total_penalty_b
