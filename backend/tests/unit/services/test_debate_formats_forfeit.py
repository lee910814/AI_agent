"""debate_formats 헬퍼 함수 단위 테스트 — forfeit 체크 관련."""

import pytest

from app.services.debate.format_1v1 import _has_severe_violation, _update_accumulated_violations


def _make_review(violations: list[dict], logic_score: int = 5) -> dict:
    return {"violations": violations, "logic_score": logic_score}


class TestHasSevereViolation:
    """_has_severe_violation() — severe 위반 존재 여부 판별."""

    def test_has_severe_violation_true(self):
        """severity=severe인 위반이 하나 이상 있으면 True를 반환한다."""
        review = _make_review([{"type": "repetition", "severity": "severe"}])
        assert _has_severe_violation(review) is True

    def test_has_severe_violation_false_minor_only(self):
        """minor 위반만 있으면 False를 반환한다."""
        review = _make_review([{"type": "ad_hominem", "severity": "minor"}])
        assert _has_severe_violation(review) is False

    def test_has_severe_violation_false_empty(self):
        """violations 배열이 비어 있으면 False를 반환한다."""
        review = _make_review([])
        assert _has_severe_violation(review) is False

    def test_has_severe_violation_mixed_returns_true(self):
        """minor와 severe가 섞여 있을 때 severe가 하나라도 있으면 True를 반환한다."""
        review = _make_review([
            {"type": "off_topic", "severity": "minor"},
            {"type": "straw_man", "severity": "severe"},
        ])
        assert _has_severe_violation(review) is True


class TestUpdateAccumulatedViolations:
    """_update_accumulated_violations() — 위반 카운트 누적 동작."""

    def test_update_accumulated_violations_adds_counts(self):
        """violations 목록을 처리하면 각 타입 카운트가 accumulated에 추가된다."""
        accumulated: dict[str, int] = {}
        review = _make_review([
            {"type": "off_topic", "severity": "severe"},
            {"type": "repetition", "severity": "minor"},
            {"type": "off_topic", "severity": "minor"},
        ])
        _update_accumulated_violations(accumulated, review)

        assert accumulated["off_topic"] == 2
        assert accumulated["repetition"] == 1

    def test_update_accumulated_violations_multiple_calls(self):
        """반복 호출 시 이전 호출 결과에 카운트가 누적된다."""
        accumulated: dict[str, int] = {}
        review_1 = _make_review([{"type": "ad_hominem", "severity": "severe"}])
        review_2 = _make_review([{"type": "ad_hominem", "severity": "minor"}])

        _update_accumulated_violations(accumulated, review_1)
        _update_accumulated_violations(accumulated, review_2)

        assert accumulated["ad_hominem"] == 2

    def test_update_accumulated_violations_empty_violations(self):
        """violations 배열이 비어 있으면 accumulated가 변경되지 않는다."""
        accumulated: dict[str, int] = {"off_topic": 1}
        review = _make_review([])
        _update_accumulated_violations(accumulated, review)

        assert accumulated == {"off_topic": 1}
