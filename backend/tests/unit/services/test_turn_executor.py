"""TurnExecutor 단위 테스트. LLM 호출, 재시도, APIKeyError 처리."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.debate.exceptions import MatchVoidError
from app.services.debate.turn_executor import TurnExecutor
from app.services.llm.providers.base import APIKeyError


def _make_agent(provider: str = "openai") -> MagicMock:
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.owner_id = uuid.uuid4()
    agent.provider = provider
    agent.model_id = "gpt-4o-mini"
    agent.name = "테스트 에이전트"
    agent.elo_rating = 1500
    return agent


def _make_match() -> MagicMock:
    match = MagicMock()
    match.id = uuid.uuid4()
    match.is_test = False
    match.season_id = None
    match.tournament_id = None
    return match


def _make_topic() -> MagicMock:
    topic = MagicMock()
    topic.title = "AI는 위험한가"
    topic.description = "AI의 위험성에 대한 토론"
    topic.max_turns = 4
    topic.turn_token_limit = 500
    topic.tools_enabled = False
    return topic


def _make_turn_log(turn_number: int = 1, speaker: str = "agent_a") -> MagicMock:
    turn = MagicMock()
    turn.id = uuid.uuid4()
    turn.turn_number = turn_number
    turn.speaker = speaker
    turn.claim = "테스트 주장"
    turn.evidence = None
    turn.action = "argue"
    turn.penalties = None
    turn.penalty_total = 0
    turn.is_blocked = False
    turn.review_result = None
    turn.response_time_ms = 100
    turn.input_tokens = 50
    turn.output_tokens = 100
    return turn


def _make_stream_chunks(text: str):
    """LLM 스트리밍 응답을 흉내내는 async generator."""
    import json

    async def _gen():
        payload = json.dumps({"action": "argue", "claim": text}, ensure_ascii=False)
        for ch in payload:
            yield ch

    return _gen()


class TestTurnExecutorExecute:
    """TurnExecutor.execute() 정상 경로 테스트."""

    @pytest.mark.asyncio
    async def test_execute_정상_LLM호출_TurnLog반환(self):
        """openai 에이전트가 정상적으로 LLM을 호출하면 DebateTurnLog를 반환한다."""
        import json

        db = AsyncMock()
        client = AsyncMock()
        agent = _make_agent(provider="openai")
        match = _make_match()
        topic = _make_topic()

        full_response = json.dumps(
            {"action": "argue", "claim": "AI는 교육을 혁신한다.", "evidence": "30% 향상 연구 있음"},
            ensure_ascii=False,
        )

        async def fake_stream(*args, **kwargs):
            usage_out = kwargs.get("usage_out", {})
            usage_out["input_tokens"] = 50
            usage_out["output_tokens"] = 100
            usage_out["finish_reason"] = "stop"
            for ch in full_response:
                yield ch

        client.generate_stream_byok = fake_stream

        with (
            patch("app.services.debate.debate_formats._log_orchestrator_usage", new_callable=AsyncMock),
            patch("app.services.debate.turn_executor.publish_event", new_callable=AsyncMock),
            patch("app.services.debate.turn_executor.settings") as mock_settings,
        ):
            mock_settings.debate_turn_timeout_seconds = 30
            mock_settings.debate_turn_max_retries = 2
            mock_settings.debate_tool_use_enabled = False  # tool-use 비활성화 — 기존 경로 테스트

            executor = TurnExecutor(client=client, db=db)
            result = await executor.execute(
                match=match,
                topic=topic,
                turn_number=1,
                speaker="agent_a",
                agent=agent,
                version=None,
                api_key="test-api-key",
                my_claims=[],
                opponent_claims=[],
            )

        assert result is not None
        assert result.turn_number == 1
        assert result.speaker == "agent_a"
        assert result.claim == "AI는 교육을 혁신한다."
        assert result.action == "argue"
        assert result.penalty_total == 0
        db.add.assert_called_once()
        db.flush.assert_called_once()


class TestTurnExecutorExecuteWithRetry:
    """TurnExecutor.execute_with_retry() 재시도 로직 테스트."""

    @pytest.mark.asyncio
    async def test_execute_with_retry_APIKeyError_재시도후무효화(self):
        """APIKeyError 발생 시 1회 재시도 후 연속 실패하면 MatchVoidError를 발생시킨다."""
        db = AsyncMock()
        client = AsyncMock()
        agent = _make_agent(provider="openai")

        with (
            patch(
                "app.services.debate.turn_executor.TurnExecutor.execute",
                new_callable=AsyncMock,
                side_effect=APIKeyError("Invalid API key"),
            ),
            patch("app.services.debate.turn_executor.settings") as mock_settings,
            patch("app.services.debate.turn_executor.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.debate_turn_max_retries = 3

            executor = TurnExecutor(client=client, db=db)
            with pytest.raises(MatchVoidError):
                await executor.execute_with_retry(
                    match=_make_match(),
                    topic=_make_topic(),
                    turn_number=1,
                    speaker="agent_a",
                    agent=agent,
                    version=None,
                    api_key="invalid-key",
                    my_claims=[],
                    opponent_claims=[],
                )

        # attempt=0: sleep 후 continue, attempt=1: MatchVoidError — execute는 2번 호출돼야 함

    @pytest.mark.asyncio
    async def test_execute_with_retry_타임아웃_재시도_후실패(self):
        """asyncio.TimeoutError 발생 시 max_retries까지 재시도한 뒤 None을 반환한다."""
        db = AsyncMock()
        client = AsyncMock()
        agent = _make_agent(provider="openai")
        call_count = 0

        async def always_timeout(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise TimeoutError("LLM 응답 없음")

        with (
            patch("app.services.debate.turn_executor.TurnExecutor.execute", side_effect=always_timeout),
            patch("app.services.debate.turn_executor.settings") as mock_settings,
        ):
            mock_settings.debate_turn_max_retries = 2

            executor = TurnExecutor(client=client, db=db)
            result = await executor.execute_with_retry(
                match=_make_match(),
                topic=_make_topic(),
                turn_number=1,
                speaker="agent_b",
                agent=agent,
                version=None,
                api_key="test-key",
                my_claims=[],
                opponent_claims=[],
            )

        assert result is None
        # max_retries=2 → 총 3번 시도 (첫 시도 + 2번 재시도)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_첫시도성공_즉시반환(self):
        """첫 시도에 성공하면 재시도 없이 TurnLog를 바로 반환한다."""
        db = AsyncMock()
        client = AsyncMock()
        expected_turn = _make_turn_log()

        with (
            patch(
                "app.services.debate.turn_executor.TurnExecutor.execute",
                new_callable=AsyncMock,
                return_value=expected_turn,
            ),
            patch("app.services.debate.turn_executor.settings") as mock_settings,
        ):
            mock_settings.debate_turn_max_retries = 2

            executor = TurnExecutor(client=client, db=db)
            result = await executor.execute_with_retry(
                match=_make_match(),
                topic=_make_topic(),
                turn_number=1,
                speaker="agent_a",
                agent=_make_agent(),
                version=None,
                api_key="test-key",
                my_claims=[],
                opponent_claims=[],
            )

        assert result is expected_turn
