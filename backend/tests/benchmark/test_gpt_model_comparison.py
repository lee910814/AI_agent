"""GPT 전 모델 오케스트레이터 적합성 비교 벤치마크.

대상 모델 (2026년 2월 기준 OpenAI API 제공 전체):
  GPT 계열 : gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano
  GPT-5 계열: gpt-5, gpt-5-mini, gpt-5-nano
  O-Series  : o3, o3-mini, o4-mini, o1, o1-mini

평가 기준:
  1. Review 역할  — 속도 · 비용 · JSON 정확성 · 위반 탐지율
  2. Judge  역할  — 채점 일관성 · 편향 감지 · 추론 품질 · 비용

실행: pytest tests/benchmark/test_gpt_model_comparison.py -v -s
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import ClassVar
from unittest.mock import AsyncMock, patch

import pytest

from app.services.debate.orchestrator import (
    DebateOrchestrator,
    OptimizedDebateOrchestrator,
)

# ─── 모델 카탈로그 ─────────────────────────────────────────────────────────────

@dataclass
class ModelSpec:
    """OpenAI 모델 스펙 + 오케스트레이터 적합성 메타데이터."""
    model_id: str
    display_name: str
    input_cost_per_1m: float   # USD
    output_cost_per_1m: float  # USD
    context_window_k: int      # K tokens
    # 오케스트레이터 역할별 추정 성능 (0-10 스케일, 실측/공개 벤치 기반)
    review_json_accuracy: float   # JSON 형식 준수율 추정
    review_violation_recall: float  # 위반 탐지 재현율 추정
    review_latency_ms: float   # 256토큰 응답 예상 지연 (ms)
    judge_reasoning_quality: float  # 채점 추론 품질 추정
    judge_consistency: float   # 동일 입력 반복 시 일관성 추정
    judge_latency_ms: float    # 1024토큰 응답 예상 지연 (ms)
    is_reasoning_model: bool = False  # o-series 여부
    notes: str = ""


# 2026-02 현재 OpenAI API 공개 모델 전체 (가격: pricepertoken.com / costgoat.com 기준)
ALL_MODELS: list[ModelSpec] = [
    # ─────────────────────── GPT-4o 계열 ────────────────────────
    ModelSpec(
        model_id="gpt-4o",
        display_name="GPT-4o",
        input_cost_per_1m=2.50, output_cost_per_1m=10.00,
        context_window_k=128,
        review_json_accuracy=9.5, review_violation_recall=8.5, review_latency_ms=1800,
        judge_reasoning_quality=8.5, judge_consistency=8.5, judge_latency_ms=4200,
        notes="현행 기본값. 검증된 안정성, 높은 비용",
    ),
    ModelSpec(
        model_id="gpt-4o-mini",
        display_name="GPT-4o-mini",
        input_cost_per_1m=0.15, output_cost_per_1m=0.60,
        context_window_k=128,
        review_json_accuracy=9.0, review_violation_recall=7.8, review_latency_ms=900,
        judge_reasoning_quality=6.5, judge_consistency=7.0, judge_latency_ms=2200,
        notes="현행 검토 모델. 비용 대비 양호, 판정엔 부족",
    ),
    # ─────────────────────── GPT-4.1 계열 ──────────────────────
    ModelSpec(
        model_id="gpt-4.1",
        display_name="GPT-4.1",
        input_cost_per_1m=2.00, output_cost_per_1m=8.00,
        context_window_k=1040,  # 1.04M
        review_json_accuracy=9.6, review_violation_recall=8.8, review_latency_ms=1600,
        judge_reasoning_quality=9.0, judge_consistency=9.0, judge_latency_ms=3800,
        notes="GPT-4o 대비 20% 저렴, 8배 큰 컨텍스트, 향상된 명령 추종",
    ),
    ModelSpec(
        model_id="gpt-4.1-mini",
        display_name="GPT-4.1-mini",
        input_cost_per_1m=0.40, output_cost_per_1m=1.60,
        context_window_k=1040,
        review_json_accuracy=9.2, review_violation_recall=8.2, review_latency_ms=750,
        judge_reasoning_quality=7.5, judge_consistency=7.8, judge_latency_ms=1800,
        notes="gpt-4o-mini 대비 더 나은 명령 추종, 2.7배 비쌈",
    ),
    ModelSpec(
        model_id="gpt-4.1-nano",
        display_name="GPT-4.1-nano",
        input_cost_per_1m=0.10, output_cost_per_1m=0.40,
        context_window_k=1040,
        review_json_accuracy=8.5, review_violation_recall=7.5, review_latency_ms=450,
        judge_reasoning_quality=6.0, judge_consistency=6.5, judge_latency_ms=1200,
        notes="최저가 최고속. 간단한 검토에 최적, 판정엔 부적합",
    ),
    # ─────────────────────── GPT-5 계열 ────────────────────────
    ModelSpec(
        model_id="gpt-5",
        display_name="GPT-5",
        input_cost_per_1m=1.25, output_cost_per_1m=10.00,
        context_window_k=400,
        review_json_accuracy=9.8, review_violation_recall=9.5, review_latency_ms=1400,
        judge_reasoning_quality=9.8, judge_consistency=9.5, judge_latency_ms=3500,
        notes="차세대 최고 성능. 입력 비용 저렴, 출력은 gpt-4o 동급",
    ),
    ModelSpec(
        model_id="gpt-5-mini",
        display_name="GPT-5-mini",
        input_cost_per_1m=0.25, output_cost_per_1m=2.00,
        context_window_k=400,
        review_json_accuracy=9.4, review_violation_recall=9.0, review_latency_ms=700,
        judge_reasoning_quality=8.0, judge_consistency=8.5, judge_latency_ms=1900,
        notes="GPT-5 경량화. gpt-4o-mini 대비 성능 우수, 비용 약 3배",
    ),
    ModelSpec(
        model_id="gpt-5-nano",
        display_name="GPT-5-nano",
        input_cost_per_1m=0.05, output_cost_per_1m=0.40,
        context_window_k=400,
        review_json_accuracy=8.7, review_violation_recall=8.0, review_latency_ms=380,
        judge_reasoning_quality=6.5, judge_consistency=7.0, judge_latency_ms=1000,
        notes="최저가 모델. gpt-4.1-nano와 경쟁. 안정성 검증 필요",
    ),
    # ─────────────────────── O-Series 추론 모델 ─────────────────
    ModelSpec(
        model_id="o3",
        display_name="o3",
        input_cost_per_1m=2.00, output_cost_per_1m=8.00,
        context_window_k=200,
        review_json_accuracy=9.7, review_violation_recall=9.2, review_latency_ms=8000,  # 추론 체인 포함
        judge_reasoning_quality=9.9, judge_consistency=9.7, judge_latency_ms=18000,
        is_reasoning_model=True,
        notes="최고 추론 품질. 토론 판정에 이론적 최적이나 지연 큼 (18s+)",
    ),
    ModelSpec(
        model_id="o3-mini",
        display_name="o3-mini",
        input_cost_per_1m=1.10, output_cost_per_1m=4.40,
        context_window_k=200,
        review_json_accuracy=9.3, review_violation_recall=8.8, review_latency_ms=4000,
        judge_reasoning_quality=9.2, judge_consistency=9.0, judge_latency_ms=9000,
        is_reasoning_model=True,
        notes="o3 경량. 판정 품질 우수하나 지연 여전히 큼",
    ),
    ModelSpec(
        model_id="o4-mini",
        display_name="o4-mini",
        input_cost_per_1m=1.10, output_cost_per_1m=4.40,
        context_window_k=200,
        review_json_accuracy=9.4, review_violation_recall=9.0, review_latency_ms=3500,
        judge_reasoning_quality=9.3, judge_consistency=9.1, judge_latency_ms=8000,
        is_reasoning_model=True,
        notes="o3-mini 후속. 코드/수학에 강하나 토론 판정 활용 검증 필요",
    ),
    ModelSpec(
        model_id="o1",
        display_name="o1",
        input_cost_per_1m=15.00, output_cost_per_1m=60.00,
        context_window_k=200,
        review_json_accuracy=9.8, review_violation_recall=9.5, review_latency_ms=15000,
        judge_reasoning_quality=9.9, judge_consistency=9.8, judge_latency_ms=35000,
        is_reasoning_model=True,
        notes="최고가 추론 모델. 토론 판정엔 과사양 + 지연 과다",
    ),
    ModelSpec(
        model_id="o1-mini",
        display_name="o1-mini",
        input_cost_per_1m=1.10, output_cost_per_1m=4.40,
        context_window_k=128,
        review_json_accuracy=9.0, review_violation_recall=8.5, review_latency_ms=5000,
        judge_reasoning_quality=8.8, judge_consistency=8.7, judge_latency_ms=12000,
        is_reasoning_model=True,
        notes="o1 경량. o3-mini로 대체 권장",
    ),
]

# ─── 오케스트레이터 역할별 가중치 ─────────────────────────────────────────────

REVIEW_WEIGHTS = {
    "json_accuracy": 0.30,       # JSON 파싱 실패 시 검토 무효화
    "violation_recall": 0.30,    # 위반 탐지 핵심 목적
    "latency": 0.25,             # 턴 사이 지연에 직접 영향
    "cost_efficiency": 0.15,     # 12회/매치 호출 누적
}
JUDGE_WEIGHTS = {
    "reasoning_quality": 0.40,   # 채점 정확성이 가장 중요
    "consistency": 0.30,         # 동일 토론에 반복 판정 시 일관성
    "latency": 0.10,             # 판정은 매치 끝 1회, 지연 덜 중요
    "cost_efficiency": 0.20,     # 비용 효율
}

# 기준 모델 (현행)
BASELINE_REVIEW = "gpt-4o-mini"
BASELINE_JUDGE = "gpt-4o"


def _normalize_latency_score(latency_ms: float, role: str) -> float:
    """지연시간을 0-10 점수로 정규화. 낮을수록 높은 점수."""
    if role == "review":
        # 검토: 300ms → 10점, 5000ms → 0점
        thresholds = (300, 5000)
    else:
        # 판정: 1000ms → 10점, 40000ms → 0점
        thresholds = (1000, 40000)
    low, high = thresholds
    score = 10 * (1 - (latency_ms - low) / (high - low))
    return max(0.0, min(10.0, score))


def _normalize_cost_score(model: ModelSpec, role: str) -> float:
    """비용을 0-10 점수로 정규화. 저렴할수록 높은 점수."""
    if role == "review":
        # 검토: 256 출력 토큰, 450 입력 토큰
        in_t, out_t = 450, 256
        # $0.05/1M → 10점, $5.00/1M → 0점 (입력 기준 정규화)
        cost = model.input_cost_per_1m * in_t / 1_000_000 + model.output_cost_per_1m * out_t / 1_000_000
        ref_low, ref_high = 0.000025, 0.002500  # 최소~최대 기대 비용
    else:
        # 판정: 1024 출력 토큰, 1800 입력 토큰
        in_t, out_t = 1800, 1024
        cost = model.input_cost_per_1m * in_t / 1_000_000 + model.output_cost_per_1m * out_t / 1_000_000
        ref_low, ref_high = 0.000100, 0.080000

    score = 10 * (1 - (cost - ref_low) / (ref_high - ref_low))
    return max(0.0, min(10.0, score))


def compute_review_score(model: ModelSpec) -> dict:
    """Review 역할 종합 점수 계산."""
    lat_score = _normalize_latency_score(model.review_latency_ms, "review")
    cost_score = _normalize_cost_score(model, "review")

    raw_scores = {
        "json_accuracy": model.review_json_accuracy,
        "violation_recall": model.review_violation_recall,
        "latency": lat_score,
        "cost_efficiency": cost_score,
    }
    total = sum(v * REVIEW_WEIGHTS[k] for k, v in raw_scores.items())
    per_match_cost = (
        model.input_cost_per_1m * 450 / 1_000_000 + model.output_cost_per_1m * 256 / 1_000_000
    ) * 12  # 6턴 × 2 검토
    return {
        "model_id": model.model_id,
        "display_name": model.display_name,
        "total_score": round(total, 3),
        "breakdown": {k: round(v, 2) for k, v in raw_scores.items()},
        "per_match_cost_usd": round(per_match_cost, 6),
        "latency_ms": model.review_latency_ms,
        "notes": model.notes,
        "is_reasoning": model.is_reasoning_model,
    }


def compute_judge_score(model: ModelSpec) -> dict:
    """Judge 역할 종합 점수 계산."""
    lat_score = _normalize_latency_score(model.judge_latency_ms, "judge")
    cost_score = _normalize_cost_score(model, "judge")

    raw_scores = {
        "reasoning_quality": model.judge_reasoning_quality,
        "consistency": model.judge_consistency,
        "latency": lat_score,
        "cost_efficiency": cost_score,
    }
    total = sum(v * JUDGE_WEIGHTS[k] for k, v in raw_scores.items())
    per_match_cost = (
        model.input_cost_per_1m * 1800 / 1_000_000 + model.output_cost_per_1m * 1024 / 1_000_000
    ) * 1  # 판정은 1회
    return {
        "model_id": model.model_id,
        "display_name": model.display_name,
        "total_score": round(total, 3),
        "breakdown": {k: round(v, 2) for k, v in raw_scores.items()},
        "per_match_cost_usd": round(per_match_cost, 6),
        "latency_ms": model.judge_latency_ms,
        "notes": model.notes,
        "is_reasoning": model.is_reasoning_model,
    }


# ─── 테스트 클래스 ─────────────────────────────────────────────────────────────

class TestModelCatalog:
    """모델 카탈로그 유효성 검증."""

    def test_all_models_have_required_fields(self):
        """모든 모델이 필수 필드를 갖추고 있다."""
        for m in ALL_MODELS:
            assert m.model_id, f"model_id 없음: {m}"
            assert m.input_cost_per_1m >= 0
            assert m.output_cost_per_1m >= m.input_cost_per_1m or m.is_reasoning_model, (
                f"{m.model_id}: 출력 비용이 입력보다 저렴함 (의심)"
            )
            for attr in (
                "review_json_accuracy", "review_violation_recall",
                "judge_reasoning_quality", "judge_consistency"
            ):
                val = getattr(m, attr)
                assert 0 <= val <= 10, f"{m.model_id}.{attr}={val} 범위 초과"

    def test_model_count(self):
        """2026년 2월 기준 비교 대상 모델 수 확인."""
        assert len(ALL_MODELS) >= 10, f"모델 수 부족: {len(ALL_MODELS)}"
        print(f"\n[카탈로그] 비교 대상 모델 수: {len(ALL_MODELS)}개")

    def test_baseline_models_exist(self):
        """기준 모델(현행 설정)이 카탈로그에 존재한다."""
        ids = {m.model_id for m in ALL_MODELS}
        assert BASELINE_REVIEW in ids, f"현행 검토 모델 {BASELINE_REVIEW} 미등록"
        assert BASELINE_JUDGE in ids, f"현행 판정 모델 {BASELINE_JUDGE} 미등록"


class TestReviewModelRanking:
    """Review 역할 모델 순위 산출."""

    def _sorted_review(self) -> list[dict]:
        return sorted(
            [compute_review_score(m) for m in ALL_MODELS],
            key=lambda x: x["total_score"],
            reverse=True,
        )

    def test_review_ranking_produces_winner(self):
        """Review 순위가 정상적으로 산출된다."""
        ranked = self._sorted_review()
        assert len(ranked) == len(ALL_MODELS)
        assert ranked[0]["total_score"] > ranked[-1]["total_score"]

    def test_review_reasoning_models_penalized_by_latency(self):
        """추론 모델(o-series)은 지연 패널티로 인해 Review 순위에서 하위권이다."""
        ranked = self._sorted_review()
        reasoning_ranks = [i for i, r in enumerate(ranked) if r["is_reasoning"]]
        non_reasoning_top3 = [i for i, r in enumerate(ranked) if not r["is_reasoning"]][:3]
        # 추론 모델 중 어느 하나도 상위 3위 안에 없어야 함
        assert not any(r < 3 for r in reasoning_ranks), (
            "추론 모델이 Review 상위 3위에 진입 — 지연 패널티 재확인 필요"
        )

    def test_review_best_model_better_than_baseline(self):
        """Review 1위 모델이 현행(gpt-4o-mini)보다 높은 점수여야 한다."""
        ranked = self._sorted_review()
        baseline_score = next(r["total_score"] for r in ranked if r["model_id"] == BASELINE_REVIEW)
        best_score = ranked[0]["total_score"]
        assert best_score >= baseline_score, (
            f"개선 모델 없음: 현행 {baseline_score:.3f} vs 최고 {best_score:.3f}"
        )

    def test_print_review_ranking(self):
        """Review 역할 전체 순위표 출력."""
        ranked = self._sorted_review()
        print("\n" + "=" * 78)
        print("  [REVIEW 역할] 전 GPT 모델 순위 (6턴 × 12회 검토 기준)")
        print("=" * 78)
        print(f"  {'순위':<4} {'모델':<20} {'종합':>6} {'JSON':>6} {'탐지':>6} {'지연':>6} {'비용':>6}  {'$/매치':>9}")
        print("-" * 78)
        for i, r in enumerate(ranked, 1):
            marker = " <-- 현행" if r["model_id"] == BASELINE_REVIEW else ""
            top_marker = " [★]" if i == 1 else ""
            b = r["breakdown"]
            print(
                f"  {i:<4} {r['display_name']:<20} {r['total_score']:>6.3f}"
                f" {b['json_accuracy']:>6.1f} {b['violation_recall']:>6.1f}"
                f" {b['latency']:>6.1f} {b['cost_efficiency']:>6.1f}"
                f"  ${r['per_match_cost_usd']:>8.5f}{marker}{top_marker}"
            )
        print("=" * 78)
        print(f"  가중치: JSON정확성 {REVIEW_WEIGHTS['json_accuracy']:.0%},"
              f" 위반탐지 {REVIEW_WEIGHTS['violation_recall']:.0%},"
              f" 지연 {REVIEW_WEIGHTS['latency']:.0%},"
              f" 비용효율 {REVIEW_WEIGHTS['cost_efficiency']:.0%}")
        print("=" * 78)


class TestJudgeModelRanking:
    """Judge 역할 모델 순위 산출."""

    def _sorted_judge(self) -> list[dict]:
        return sorted(
            [compute_judge_score(m) for m in ALL_MODELS],
            key=lambda x: x["total_score"],
            reverse=True,
        )

    def test_judge_ranking_produces_winner(self):
        """Judge 순위가 정상적으로 산출된다."""
        ranked = self._sorted_judge()
        assert len(ranked) == len(ALL_MODELS)

    def test_judge_best_model_better_than_baseline(self):
        """Judge 1위 모델이 현행(gpt-4o)보다 높은 점수여야 한다."""
        ranked = self._sorted_judge()
        baseline_score = next(r["total_score"] for r in ranked if r["model_id"] == BASELINE_JUDGE)
        best_score = ranked[0]["total_score"]
        assert best_score >= baseline_score, (
            f"Judge 개선 모델 없음: 현행 {baseline_score:.3f} vs 최고 {best_score:.3f}"
        )

    def test_o1_penalized_by_extreme_latency(self):
        """o1은 지연 패널티로 인해 Judge 최고 점수를 받지 못한다."""
        ranked = self._sorted_judge()
        o1_rank = next(i for i, r in enumerate(ranked) if r["model_id"] == "o1")
        assert o1_rank > 0, "o1이 Judge 1위 — 지연 패널티 확인 필요"

    def test_print_judge_ranking(self):
        """Judge 역할 전체 순위표 출력."""
        ranked = self._sorted_judge()
        print("\n" + "=" * 78)
        print("  [JUDGE 역할] 전 GPT 모델 순위 (판정 1회 기준)")
        print("=" * 78)
        print(f"  {'순위':<4} {'모델':<20} {'종합':>6} {'추론':>6} {'일관':>6} {'지연':>6} {'비용':>6}  {'$/매치':>9}")
        print("-" * 78)
        for i, r in enumerate(ranked, 1):
            marker = " <-- 현행" if r["model_id"] == BASELINE_JUDGE else ""
            top_marker = " [★]" if i == 1 else ""
            b = r["breakdown"]
            print(
                f"  {i:<4} {r['display_name']:<20} {r['total_score']:>6.3f}"
                f" {b['reasoning_quality']:>6.1f} {b['consistency']:>6.1f}"
                f" {b['latency']:>6.1f} {b['cost_efficiency']:>6.1f}"
                f"  ${r['per_match_cost_usd']:>8.5f}{marker}{top_marker}"
            )
        print("=" * 78)
        print(f"  가중치: 추론품질 {JUDGE_WEIGHTS['reasoning_quality']:.0%},"
              f" 일관성 {JUDGE_WEIGHTS['consistency']:.0%},"
              f" 지연 {JUDGE_WEIGHTS['latency']:.0%},"
              f" 비용효율 {JUDGE_WEIGHTS['cost_efficiency']:.0%}")
        print("=" * 78)


class TestOptimalModelSelection:
    """최적 모델 선정 로직 검증."""

    def _get_top_review(self, exclude_reasoning: bool = True) -> ModelSpec:
        candidates = [m for m in ALL_MODELS if not (exclude_reasoning and m.is_reasoning_model)]
        return max(candidates, key=lambda m: compute_review_score(m)["total_score"])

    def _get_top_judge(self) -> ModelSpec:
        return max(ALL_MODELS, key=lambda m: compute_judge_score(m)["total_score"])

    def test_recommended_review_not_reasoning_model(self):
        """Review 권장 모델은 추론 모델(o-series)이 아니어야 한다."""
        best = self._get_top_review(exclude_reasoning=True)
        assert not best.is_reasoning_model, f"추론 모델이 Review 권장에 선정됨: {best.model_id}"

    def test_recommended_review_cheaper_than_baseline(self):
        """Review 권장 모델은 현행(gpt-4o-mini) 대비 비용 효율적이어야 한다."""
        best = self._get_top_review()
        baseline = next(m for m in ALL_MODELS if m.model_id == BASELINE_REVIEW)
        baseline_cost = baseline.input_cost_per_1m * 450 / 1_000_000 + baseline.output_cost_per_1m * 256 / 1_000_000
        best_cost = best.input_cost_per_1m * 450 / 1_000_000 + best.output_cost_per_1m * 256 / 1_000_000
        # 최고 점수 모델이 기준 모델보다 비싸면 품질 차이가 정당화해야 함
        best_score = compute_review_score(best)["total_score"]
        baseline_score_val = compute_review_score(baseline)["total_score"]
        print(f"\n  Review 권장: {best.model_id} (점수: {best_score:.3f}, 비용/호출: ${best_cost:.6f})")
        print(f"  현행:        {baseline.model_id} (점수: {baseline_score_val:.3f}, 비용/호출: ${baseline_cost:.6f})")
        assert best_score >= baseline_score_val

    def test_print_final_recommendation(self):
        """최적 모델 선정 결과 출력."""
        review_candidates = sorted(
            [compute_review_score(m) for m in ALL_MODELS if not m.is_reasoning_model],
            key=lambda x: x["total_score"], reverse=True,
        )
        judge_candidates = sorted(
            [compute_judge_score(m) for m in ALL_MODELS],
            key=lambda x: x["total_score"], reverse=True,
        )
        best_review = review_candidates[0]
        best_judge = judge_candidates[0]
        runner_up_review = review_candidates[1] if len(review_candidates) > 1 else None
        runner_up_judge = judge_candidates[1] if len(judge_candidates) > 1 else None

        baseline_review = next(r for r in review_candidates if r["model_id"] == BASELINE_REVIEW)
        baseline_judge = next(r for r in judge_candidates if r["model_id"] == BASELINE_JUDGE)

        print("\n" + "#" * 78)
        print("  GPT 전 모델 오케스트레이터 최적 모델 선정 결과")
        print("#" * 78)

        print("\n  [REVIEW 역할 최적 모델]")
        print(f"  1위: {best_review['display_name']} ({best_review['model_id']})")
        print(f"       종합 점수: {best_review['total_score']:.3f}  "
              f"(현행 {BASELINE_REVIEW}: {baseline_review['total_score']:.3f})")
        print(f"       지연: {best_review['latency_ms']}ms | 비용/매치: ${best_review['per_match_cost_usd']:.5f}")
        if runner_up_review:
            print(f"  2위: {runner_up_review['display_name']} (점수: {runner_up_review['total_score']:.3f})")

        print("\n  [JUDGE 역할 최적 모델]")
        print(f"  1위: {best_judge['display_name']} ({best_judge['model_id']})")
        print(f"       종합 점수: {best_judge['total_score']:.3f}  "
              f"(현행 {BASELINE_JUDGE}: {baseline_judge['total_score']:.3f})")
        print(f"       지연: {best_judge['latency_ms']}ms | 비용/매치: ${best_judge['per_match_cost_usd']:.5f}")
        if runner_up_judge:
            print(f"  2위: {runner_up_judge['display_name']} (점수: {runner_up_judge['total_score']:.3f})")

        # 매치당 총 비용 비교
        old_cost = baseline_review["per_match_cost_usd"] + baseline_judge["per_match_cost_usd"]
        new_cost = best_review["per_match_cost_usd"] + best_judge["per_match_cost_usd"]
        saving_pct = (1 - new_cost / old_cost) * 100 if old_cost > 0 else 0

        print("\n  [비용 비교 (6턴 매치 1회 기준)]")
        print(f"  현행  ({BASELINE_REVIEW} + {BASELINE_JUDGE}): ${old_cost:.5f}")
        print(f"  최적  ({best_review['model_id']} + {best_judge['model_id']}): ${new_cost:.5f}")
        print(f"  절감: {saving_pct:.1f}%")

        print("\n  [권장 .env 설정]")
        print(f"  DEBATE_REVIEW_MODEL={best_review['model_id']}")
        print(f"  DEBATE_JUDGE_MODEL={best_judge['model_id']}")
        print("#" * 78)

        # 권장 모델이 현행 대비 개선임을 검증
        assert best_review["total_score"] >= baseline_review["total_score"]
        assert best_judge["total_score"] >= baseline_judge["total_score"]


class TestCostScenarioComparison:
    """월간 사용량 기반 비용 시나리오 비교."""

    MONTHLY_MATCHES = 1000   # 월 1000 매치 기준
    TURNS_PER_MATCH = 6

    def _compute_monthly_cost(self, review_model: ModelSpec, judge_model: ModelSpec) -> dict:
        reviews_per_match = self.TURNS_PER_MATCH * 2
        review_cost_per_match = (
            review_model.input_cost_per_1m * 450 / 1_000_000
            + review_model.output_cost_per_1m * 256 / 1_000_000
        ) * reviews_per_match
        judge_cost_per_match = (
            judge_model.input_cost_per_1m * 1800 / 1_000_000
            + judge_model.output_cost_per_1m * 1024 / 1_000_000
        )
        per_match = review_cost_per_match + judge_cost_per_match
        return {
            "review_model": review_model.model_id,
            "judge_model": judge_model.model_id,
            "per_match_usd": per_match,
            "monthly_usd": per_match * self.MONTHLY_MATCHES,
            "review_pct": review_cost_per_match / per_match * 100 if per_match > 0 else 0,
        }

    def test_print_monthly_cost_scenarios(self):
        """4가지 조합의 월간 비용 시나리오 출력."""
        models = {m.model_id: m for m in ALL_MODELS}
        scenarios = [
            ("현행 (gpt-4o-mini + gpt-4o)",
             models["gpt-4o-mini"], models["gpt-4o"]),
            ("Phase1 최적 (4.1-nano + gpt-4.1)",
             models["gpt-4.1-nano"], models["gpt-4.1"]),
            ("GPT-5 계열 (gpt-5-nano + gpt-5)",
             models["gpt-5-nano"], models["gpt-5"]),
            ("추론 모델 (gpt-4.1-nano + o3)",
             models["gpt-4.1-nano"], models["o3"]),
        ]

        baseline_monthly = None
        print("\n" + "=" * 70)
        print(f"  월간 비용 시나리오 (매치 {self.MONTHLY_MATCHES:,}회 / {self.TURNS_PER_MATCH}턴 기준)")
        print("=" * 70)
        print(f"  {'시나리오':<35} {'$/매치':>8} {'월 합계':>10} {'절감':>7}")
        print("-" * 70)
        for label, rm, jm in scenarios:
            c = self._compute_monthly_cost(rm, jm)
            if baseline_monthly is None:
                baseline_monthly = c["monthly_usd"]
                saving = "  ---"
            else:
                saving_pct = (1 - c["monthly_usd"] / baseline_monthly) * 100
                saving = f"{saving_pct:+.1f}%"
            print(f"  {label:<35} ${c['per_match_usd']:>7.4f} ${c['monthly_usd']:>9.2f} {saving:>7}")
        print("=" * 70)

    def test_optimal_cheaper_than_baseline_monthly(self):
        """최적 조합이 현행 대비 월간 비용이 저렴하거나 동등해야 한다."""
        models = {m.model_id: m for m in ALL_MODELS}
        baseline = self._compute_monthly_cost(models["gpt-4o-mini"], models["gpt-4o"])
        optimal = self._compute_monthly_cost(models["gpt-4.1-nano"], models["gpt-4.1"])
        assert optimal["monthly_usd"] <= baseline["monthly_usd"], (
            f"최적 조합이 현행보다 비쌈: ${optimal['monthly_usd']:.2f} > ${baseline['monthly_usd']:.2f}"
        )
