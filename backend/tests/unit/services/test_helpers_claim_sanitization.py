"""validate_response_schema claim 오염 정화 단위 테스트."""

import json

import pytest

from app.services.debate.helpers import validate_response_schema


def _make_json(claim: str, action: str = "argue") -> str:
    return json.dumps({"action": action, "claim": claim}, ensure_ascii=False)


class TestClaimSanitization:
    """validate_response_schema() claim 필드 오염 제거 동작 검증."""

    def test_clean_claim_unchanged(self):
        """오염이 없는 정상 claim은 그대로 유지된다."""
        payload = _make_json("AI는 인간보다 논리적으로 우수합니다")
        result = validate_response_schema(payload)

        assert result is not None
        assert result["claim"] == "AI는 인간보다 논리적으로 우수합니다"

    def test_claim_with_evidence_contamination(self):
        r"""claim 내부에 \nevidence: 가 포함되면 그 이전까지만 claim으로 사용한다."""
        raw_claim = "AI는 효율적입니다\nevidence: 여러 연구에서 확인됨"
        payload = _make_json(raw_claim)
        result = validate_response_schema(payload)

        assert result is not None
        assert result["claim"] == "AI는 효율적입니다"
        assert "evidence:" not in result["claim"]

    def test_claim_with_tool_used_contamination(self):
        r"""claim 내부에 \ntool_used: 가 포함되면 그 이전까지만 claim으로 사용한다."""
        raw_claim = "AI 활용이 증가하고 있습니다\ntool_used: web_search"
        payload = _make_json(raw_claim)
        result = validate_response_schema(payload)

        assert result is not None
        assert result["claim"] == "AI 활용이 증가하고 있습니다"
        assert "tool_used:" not in result["claim"]

    def test_claim_with_tool_result_contamination(self):
        r"""claim 내부에 \ntool_result: 가 포함되면 그 이전까지만 claim으로 사용한다."""
        raw_claim = "검색으로 확인했습니다\ntool_result: 검색 결과 요약"
        payload = _make_json(raw_claim)
        result = validate_response_schema(payload)

        assert result is not None
        assert result["claim"] == "검색으로 확인했습니다"
        assert "tool_result:" not in result["claim"]

    def test_claim_with_multiple_contaminations(self):
        r"""여러 오염 패턴이 있을 때 첫 번째 오염 지점에서 잘린다."""
        raw_claim = "주요 주장입니다\nevidence: 근거\ntool_used: web_search"
        payload = _make_json(raw_claim)
        result = validate_response_schema(payload)

        assert result is not None
        # 첫 번째 오염(\nevidence:)에서 잘림
        assert result["claim"] == "주요 주장입니다"

    def test_contamination_case_insensitive(self):
        r"""오염 패턴 탐지는 대소문자를 구분하지 않는다."""
        raw_claim = "AI 논증입니다\nEvidence: 대문자 시작 근거"
        payload = _make_json(raw_claim)
        result = validate_response_schema(payload)

        assert result is not None
        assert result["claim"] == "AI 논증입니다"

    def test_claim_becomes_empty_returns_none(self):
        r"""오염 제거 후 claim이 빈 문자열이 되면 None을 반환한다."""
        raw_claim = "\nevidence: 이것만 있음"
        payload = _make_json(raw_claim)
        result = validate_response_schema(payload)

        assert result is None
