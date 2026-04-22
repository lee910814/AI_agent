"""DebateOrchestrator.review_turn() accumulated_violations 주입 단위 테스트."""

import json
from unittest.mock import patch

import pytest

from app.services.debate.orchestrator import DebateOrchestrator


def _make_review_response(logic_score: int = 7) -> dict:
    return {
        "content": json.dumps({
            "logic_score": logic_score,
            "violations": [],
            "feedback": "테스트 피드백",
            "block": False,
        }),
        "input_tokens": 10,
        "output_tokens": 10,
    }


class TestAccumulatedViolationsInjection:
    """review_turn()이 accumulated_violations를 user_content에 올바르게 주입하는지 검증."""

    @pytest.mark.asyncio
    async def test_no_accumulated_violations_no_injection(self):
        """accumulated_violations=None이면 누적 위반 텍스트가 user_content에 없다."""
        orchestrator = DebateOrchestrator()
        captured_messages: list[dict] = []

        async def _mock_generate_byok(provider, model_id, api_key, messages, **kwargs):
            captured_messages.extend(messages)
            return _make_review_response()

        orchestrator.client.generate_byok = _mock_generate_byok

        with patch("app.services.debate.orchestrator._platform_api_key", return_value="sk-test"):
            await orchestrator.review_turn(
                topic="AI 규제 논쟁",
                speaker="agent_a",
                turn_number=1,
                claim="AI는 규제가 필요합니다",
                evidence=None,
                action="argue",
                accumulated_violations=None,
            )

        user_msg = next(
            (m["content"] for m in captured_messages if m["role"] == "user"), ""
        )
        assert "누적 위반" not in user_msg

    @pytest.mark.asyncio
    async def test_accumulated_violations_injected_into_prompt(self):
        """accumulated_violations가 있으면 user_content에 각 위반 타입과 카운트가 포함된다."""
        orchestrator = DebateOrchestrator()
        captured_messages: list[dict] = []

        async def _mock_generate_byok(provider, model_id, api_key, messages, **kwargs):
            captured_messages.extend(messages)
            return _make_review_response()

        orchestrator.client.generate_byok = _mock_generate_byok

        with patch("app.services.debate.orchestrator._platform_api_key", return_value="sk-test"):
            await orchestrator.review_turn(
                topic="AI 규제 논쟁",
                speaker="agent_b",
                turn_number=3,
                claim="규제는 혁신을 저해합니다",
                evidence=None,
                action="rebut",
                accumulated_violations={"off_topic": 3, "repetition": 2},
            )

        user_msg = next(
            (m["content"] for m in captured_messages if m["role"] == "user"), ""
        )
        assert "off_topic×3" in user_msg
        assert "repetition×2" in user_msg

    @pytest.mark.asyncio
    async def test_accumulated_violations_empty_dict_no_injection(self):
        """accumulated_violations가 빈 dict이면 누적 위반 텍스트가 user_content에 없다."""
        orchestrator = DebateOrchestrator()
        captured_messages: list[dict] = []

        async def _mock_generate_byok(provider, model_id, api_key, messages, **kwargs):
            captured_messages.extend(messages)
            return _make_review_response()

        orchestrator.client.generate_byok = _mock_generate_byok

        with patch("app.services.debate.orchestrator._platform_api_key", return_value="sk-test"):
            await orchestrator.review_turn(
                topic="AI 규제 논쟁",
                speaker="agent_a",
                turn_number=2,
                claim="데이터 보호가 중요합니다",
                evidence=None,
                action="argue",
                accumulated_violations={},
            )

        user_msg = next(
            (m["content"] for m in captured_messages if m["role"] == "user"), ""
        )
        assert "누적 위반" not in user_msg
