"""Debate orchestration control plane.

정책(Policy)과 런타임 컨텍스트(Context)를 분리해
토론 실행 중 의사결정(모델 선택/병렬 여부/타임아웃/재시도)과
추적 메타데이터(trace_id, fallback_reason)를 일관되게 관리한다.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)


def _stable_bucket(key: str) -> int:
    """문자열 키를 0~9999 범위 정수 버킷으로 매핑한다."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 10000


@dataclass(frozen=True)
class OrchestrationPolicy:
    """오케스트레이션 정책 스냅샷.

    런타임 중 변경되지 않는 설정값을 모아 보관한다.
    """

    mode: str
    review_timeout_seconds: int
    parallel_enabled: bool
    draw_threshold: int
    retry_budget: int
    review_enabled: bool
    review_model: str
    judge_model: str
    review_model_candidate: str
    judge_model_candidate: str
    model_rollout_ratio: float
    trace_events_enabled: bool

    @classmethod
    def from_settings(cls) -> "OrchestrationPolicy":
        ratio = min(max(settings.debate_model_rollout_ratio, 0.0), 1.0)
        return cls(
            mode=settings.debate_orchestration_mode,
            review_timeout_seconds=settings.debate_turn_review_timeout,
            parallel_enabled=settings.debate_orchestrator_optimized,
            draw_threshold=settings.debate_draw_threshold,
            retry_budget=settings.debate_turn_max_retries,
            review_enabled=settings.debate_turn_review_enabled,
            review_model=settings.debate_review_model or settings.debate_orchestrator_model,
            judge_model=settings.debate_judge_model or settings.debate_orchestrator_model,
            review_model_candidate=settings.debate_review_model_candidate,
            judge_model_candidate=settings.debate_judge_model_candidate,
            model_rollout_ratio=ratio,
            trace_events_enabled=settings.debate_trace_events_enabled,
        )


@dataclass
class OrchestrationRuntimeContext:
    """토론 1회 실행(run_debate) 동안 유지되는 컨텍스트."""

    trace_id: str
    match_id: str
    match_format: str
    mode: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    fallback_counts: dict[str, int] = field(default_factory=dict)
    transitions: list[dict[str, str]] = field(default_factory=list)


class OrchestrationControlPlane:
    """토론 실행 정책/컨텍스트를 관리하는 단일 진입점."""

    def __init__(
        self,
        match_id: str,
        match_format: str,
        policy: OrchestrationPolicy | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.policy = policy or OrchestrationPolicy.from_settings()
        mode_suffix = "parallel" if self.policy.parallel_enabled else "sequential"
        runtime_mode = f"{self.policy.mode}:{mode_suffix}"
        self.runtime = OrchestrationRuntimeContext(
            trace_id=trace_id or str(uuid4()),
            match_id=match_id,
            match_format=match_format,
            mode=runtime_mode,
        )

    def _is_in_rollout(self, lane: str) -> bool:
        """lane(review/judge) 기준 실험군 포함 여부를 결정한다."""
        if self.policy.model_rollout_ratio <= 0:
            return False
        key = f"{self.runtime.match_id}:{lane}"
        bucket = _stable_bucket(key)
        return bucket < int(self.policy.model_rollout_ratio * 10000)

    def select_review_model(self) -> str:
        """review 모델 선택(점진 롤아웃 포함)."""
        if self.policy.review_model_candidate and self._is_in_rollout("review"):
            return self.policy.review_model_candidate
        return self.policy.review_model

    def select_judge_model(self) -> str:
        """judge 모델 선택(점진 롤아웃 포함)."""
        if self.policy.judge_model_candidate and self._is_in_rollout("judge"):
            return self.policy.judge_model_candidate
        return self.policy.judge_model

    def record_transition(self, from_status: str, to_status: str, reason: str = "") -> None:
        """매치 상태 전이를 기록한다."""
        self.runtime.transitions.append({
            "from": from_status,
            "to": to_status,
            "reason": reason,
        })

    def mark_fallback(
        self,
        reason: str,
        *,
        stage: str,
        turn_number: int | None = None,
        speaker: str | None = None,
    ) -> None:
        """fallback 발생을 누적 기록한다."""
        key = f"{stage}:{reason}"
        self.runtime.fallback_counts[key] = self.runtime.fallback_counts.get(key, 0) + 1
        logger.warning(
            "Orchestration fallback | trace_id=%s match_id=%s stage=%s reason=%s turn=%s speaker=%s",
            self.runtime.trace_id,
            self.runtime.match_id,
            stage,
            reason,
            turn_number,
            speaker,
        )

    def event_meta(
        self,
        *,
        turn_number: int | None = None,
        speaker: str | None = None,
        fallback_reason: str | None = None,
    ) -> dict:
        """SSE payload에 붙일 공통 메타를 반환한다.

        trace 기능 비활성화 시 빈 dict를 반환해 기존 페이로드와 동일하게 유지한다.
        """
        if not self.policy.trace_events_enabled:
            return {}
        meta = {
            "trace_id": self.runtime.trace_id,
            "orchestration_mode": self.runtime.mode,
        }
        if turn_number is not None:
            meta["turn"] = turn_number
        if speaker:
            meta["speaker"] = speaker
        if fallback_reason:
            meta["fallback_reason"] = fallback_reason
        return meta

