"""토론 엔진 단위 테스트. JSON 스키마 검증, 벌점 감지 로직."""

import json

import pytest

from app.services.debate.helpers import (
    validate_response_schema,
)


class TestResponseSchemaValidation:
    def test_valid_response(self):
        """유효한 JSON 응답을 파싱한다."""
        response = json.dumps({
            "action": "argue",
            "claim": "AI will transform education.",
            "evidence": "Studies show 30% improvement.",
            "tool_used": None,
            "tool_result": None,
        })
        result = validate_response_schema(response)
        assert result is not None
        assert result["action"] == "argue"
        assert result["claim"] == "AI will transform education."

    def test_valid_response_in_code_block(self):
        """코드 블록 안의 JSON도 파싱한다."""
        response = '```json\n{"action": "rebut", "claim": "That is incorrect."}\n```'
        result = validate_response_schema(response)
        assert result is not None
        assert result["action"] == "rebut"

    def test_invalid_json(self):
        """잘못된 JSON은 None을 반환한다."""
        result = validate_response_schema("This is not JSON at all.")
        assert result is None

    def test_missing_required_fields(self):
        """필수 필드가 없으면 None을 반환한다."""
        response = json.dumps({"action": "argue"})  # claim 누락
        result = validate_response_schema(response)
        assert result is None

    def test_invalid_action(self):
        """잘못된 action 값은 None을 반환한다."""
        response = json.dumps({"action": "attack", "claim": "test"})
        result = validate_response_schema(response)
        assert result is None

    def test_all_valid_actions(self):
        """모든 유효한 action이 통과한다."""
        for action in ("argue", "rebut", "concede", "question", "summarize"):
            response = json.dumps({"action": action, "claim": "test"})
            result = validate_response_schema(response)
            assert result is not None


class TestLocalAgentRouting:
    """local 에이전트 관련 엔진 로직 테스트."""

    def test_valid_local_actions_accepted(self):
        """local 에이전트 응답의 유효한 action은 통과한다."""
        for action in ("argue", "rebut", "concede", "question", "summarize"):
            response = json.dumps({"action": action, "claim": "local test"})
            result = validate_response_schema(response)
            assert result is not None
            assert result["action"] == action

class TestResolveApiKey:
    def test_local_provider_returns_empty_string(self):
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock
        agent = MagicMock()
        agent.provider = "local"
        result = _resolve_api_key(agent)
        assert result == ""

    def test_platform_credits_openai(self):
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock, patch
        agent = MagicMock()
        agent.provider = "openai"
        agent.use_platform_credits = True
        with patch("app.services.debate.helpers.settings") as m:
            m.openai_api_key = "test_key"
            result = _resolve_api_key(agent)
            assert result == "test_key"

    def test_platform_credits_anthropic(self):
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock, patch
        agent = MagicMock()
        agent.provider = "anthropic"
        agent.use_platform_credits = True
        with patch("app.services.debate.helpers.settings") as m:
            m.anthropic_api_key = "test_key"
            result = _resolve_api_key(agent)
            assert result == "test_key"

    def test_byok_returns_decrypted_key(self):
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock, patch
        agent = MagicMock()
        agent.provider = "openai"
        agent.use_platform_credits = False
        agent.encrypted_api_key = "gAAAAACdef..."
        with patch("app.services.debate.helpers.decrypt_api_key") as m:
            m.return_value = "sk-user-key"
            result = _resolve_api_key(agent)
            assert result == "sk-user-key"

    def test_force_platform(self):
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock, patch
        agent = MagicMock()
        agent.provider = "anthropic"
        agent.use_platform_credits = False
        agent.encrypted_api_key = "gAAAAACdef..."
        with patch("app.services.debate.helpers.settings") as m:
            m.anthropic_api_key = "sk-platform"
            result = _resolve_api_key(agent, force_platform=True)
            assert result == "sk-platform"


class TestPredictionCutoffLogic:
    """예측 투표 컷오프 로직 테스트 (설계상 검증)."""

    def test_cutoff_configuration(self):
        """설정된 컷오프 턴 수를 확인한다."""
        from app.core.config import settings
        assert settings.debate_prediction_cutoff_turns == 2

    def test_prediction_service_has_create_prediction_method(self):
        """DebateMatchService가 create_prediction 메서드를 갖는다."""
        from app.services.debate.match_service import DebateMatchService
        assert hasattr(DebateMatchService, 'create_prediction')
        assert callable(getattr(DebateMatchService, 'create_prediction'))


class TestTurnLoopUnification:
    """통합된 단일 _run_turn_loop 함수 테스트."""

    def test_run_turn_loop_exists(self):
        """_run_turn_loop 함수가 존재한다."""
        from app.services.debate.engine import _run_turn_loop
        assert callable(_run_turn_loop)

    def test_optimized_loops_removed(self):
        """이전 개별 루프 함수들이 제거됐다."""
        import app.services.debate.engine as mod
        assert not hasattr(mod, "_run_optimized_turn_loop")
        assert not hasattr(mod, "_run_sequential_turn_loop")

    def test_run_turn_loop_accepts_parallel_flag(self):
        """_run_turn_loop이 parallel 파라미터를 받는다."""
        import inspect
        from app.services.debate.engine import _run_turn_loop
        sig = inspect.signature(_run_turn_loop)
        assert "parallel" in sig.parameters
