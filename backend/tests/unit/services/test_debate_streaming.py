"""토론 스트리밍 단위 테스트."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGenerateStreamByok:
    @pytest.mark.asyncio
    async def test_openai_byok_yields_chunks(self):
        """OpenAI BYOK 스트리밍이 청크를 yield한다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()

        chunks = [
            json.dumps({"choices": [{"delta": {"content": "안"}}]}),
            json.dumps({"choices": [{"delta": {"content": "녕"}}]}),
            json.dumps({"choices": [{"delta": {}}], "usage": {"prompt_tokens": 10, "completion_tokens": 2}}),
            "[DONE]",
        ]
        lines = ["data: " + c for c in chunks]

        async def _fake_stream(*args, **kwargs):
            for line in lines:
                yield line

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = _fake_stream
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        usage_out: dict = {}
        collected = []
        # provider 내부 HTTP 클라이언트를 교체 — 리팩터링 후 OpenAIProvider가 _http를 보유
        client._providers["openai"]._http = mock_client
        async for chunk in client._stream_openai_byok(
            "gpt-4o", "test-key", [{"role": "user", "content": "hi"}], usage_out=usage_out
        ):
            collected.append(chunk)

        assert collected == ["안", "녕"]
        assert usage_out["input_tokens"] == 10
        assert usage_out["output_tokens"] == 2

    @pytest.mark.asyncio
    async def test_generate_stream_byok_routes_to_openai(self):
        """generate_stream_byok가 openai provider의 stream_byok로 라우팅한다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()

        async def _fake_openai_stream(*args, **kwargs):
            yield "테스트"

        # 리팩터링 후: generate_stream_byok는 _providers["openai"].stream_byok에 위임
        with patch.object(client._providers["openai"], "stream_byok", side_effect=_fake_openai_stream) as mock_stream:
            result = []
            async for chunk in client.generate_stream_byok(
                provider="openai",
                model_id="gpt-4o",
                api_key="key",
                messages=[],
            ):
                result.append(chunk)

        mock_stream.assert_called_once()
        assert result == ["테스트"]

    @pytest.mark.asyncio
    async def test_generate_stream_byok_unknown_provider_raises(self):
        """지원하지 않는 provider는 ValueError를 발생시킨다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()
        with pytest.raises(ValueError, match="not supported"):
            async for _ in client.generate_stream_byok(
                provider="unknown",
                model_id="x",
                api_key="k",
                messages=[],
            ):
                pass


class TestDebateEngineStreaming:
    @pytest.mark.asyncio
    async def test_byok_turn_publishes_chunk_events(self):
        """BYOK 턴 실행 시 turn_chunk 이벤트가 각 청크마다 발행된다."""
        from decimal import Decimal
        from app.models.llm_model import LLMModel
        from app.services.debate.turn_executor import TurnExecutor

        # 테스트용 mock 객체 구성
        match = MagicMock()
        match.id = uuid.uuid4()

        topic = MagicMock()
        topic.turn_token_limit = 512
        topic.tools_enabled = False
        topic.title = "AI 토론"
        topic.description = "테스트"
        topic.max_turns = 4

        agent = MagicMock()
        agent.provider = "openai"
        agent.model_id = "gpt-4o"
        agent.id = uuid.uuid4()
        agent.owner_id = uuid.uuid4()

        version = MagicMock()
        version.system_prompt = "당신은 토론 참가자입니다."

        # LLMModel mock 설정
        mock_model = MagicMock(spec=LLMModel)
        mock_model.id = uuid.uuid4()
        mock_model.input_cost_per_1m = Decimal("0.003")
        mock_model.output_cost_per_1m = Decimal("0.006")

        # db.execute() 반환값: coroutine을 반환해야 함
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_model)

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        # 스트리밍 청크: JSON 형식 응답
        raw_json = '{"action":"argue","claim":"AI는 좋은 기술입니다.","evidence":null,"tool_used":null,"tool_result":null}'
        chunks = [raw_json[i : i + 10] for i in range(0, len(raw_json), 10)]

        async def _fake_stream(*args, **kwargs):
            for c in chunks:
                yield c
            # usage_out 설정
            if "usage_out" in kwargs and kwargs["usage_out"] is not None:
                kwargs["usage_out"]["input_tokens"] = 50
                kwargs["usage_out"]["output_tokens"] = 20

        published_events = []

        async def _fake_publish(match_id, event_type, data):
            published_events.append((event_type, data))

        with (
            patch("app.services.debate.turn_executor.publish_event", side_effect=_fake_publish),
            patch("app.services.debate.engine._log_orchestrator_usage", new_callable=AsyncMock),
        ):
            fake_client = MagicMock()
            fake_client.generate_stream_byok = _fake_stream

            executor = TurnExecutor(client=fake_client, db=db)
            turn = await executor.execute(
                match=match,
                topic=topic,
                turn_number=1,
                speaker="agent_a",
                agent=agent,
                version=version,
                api_key="test-key",
                my_claims=[],
                opponent_claims=[],
            )

        chunk_events = [e for e in published_events if e[0] == "turn_chunk"]
        assert len(chunk_events) == len(chunks), f"expected {len(chunks)} chunk events, got {len(chunk_events)}"
        assert turn.claim == "AI는 좋은 기술입니다."
        assert turn.action == "argue"
