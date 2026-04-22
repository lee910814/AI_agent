"""InferenceClient 단위 테스트. 외부 API 호출을 mock."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm.inference_client import InferenceClient


def _make_llm_model(provider: str, model_id: str = "test-model") -> MagicMock:
    model = MagicMock()
    model.provider = provider
    model.model_id = model_id
    return model


@pytest.fixture
def client():
    return InferenceClient()


MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello"},
]


class TestSplitSystemMessages:
    def test_splits_system_from_user_messages(self):
        system, api_msgs = InferenceClient._split_system_messages(MESSAGES)
        assert "helpful assistant" in system
        assert len(api_msgs) == 1
        assert api_msgs[0]["role"] == "user"

    def test_merges_multiple_system_messages(self):
        msgs = [
            {"role": "system", "content": "Rule 1"},
            {"role": "system", "content": "Rule 2"},
            {"role": "user", "content": "Hi"},
        ]
        system, api_msgs = InferenceClient._split_system_messages(msgs)
        assert "Rule 1" in system
        assert "Rule 2" in system
        assert len(api_msgs) == 1

    def test_no_system_messages(self):
        msgs = [{"role": "user", "content": "Hi"}]
        system, api_msgs = InferenceClient._split_system_messages(msgs)
        assert system == ""
        assert len(api_msgs) == 1


class TestToGeminiFormat:
    def test_converts_roles_correctly(self):
        msgs = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        system, contents = InferenceClient._to_gemini_format(msgs)
        assert "System prompt" in system
        assert len(contents) == 2
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"

    def test_user_parts_format(self):
        msgs = [{"role": "user", "content": "test"}]
        _, contents = InferenceClient._to_gemini_format(msgs)
        assert contents[0]["parts"][0]["text"] == "test"


class TestGenerateRouting:
    """generate()가 각 provider의 generate()로 올바르게 라우팅되는지 검증.

    리팩터링 후 generate()는 _providers[provider].generate()에 위임하므로
    provider 인스턴스의 generate를 직접 mock한다.
    """

    @pytest.mark.asyncio
    async def test_routes_to_openai(self, client):
        model = _make_llm_model("openai")
        with patch.object(client._providers["openai"], "generate", new_callable=AsyncMock) as mock:
            mock.return_value = {"content": "ok", "input_tokens": 10, "output_tokens": 5}
            result = await client.generate(model, MESSAGES)
            mock.assert_called_once()
            assert result["content"] == "ok"

    @pytest.mark.asyncio
    async def test_routes_to_runpod(self, client):
        model = _make_llm_model("runpod")
        with patch.object(client._providers["runpod"], "generate", new_callable=AsyncMock) as mock:
            mock.return_value = {"content": "ok", "input_tokens": 10, "output_tokens": 5}
            await client.generate(model, MESSAGES)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_to_anthropic(self, client):
        model = _make_llm_model("anthropic")
        with patch.object(client._providers["anthropic"], "generate", new_callable=AsyncMock) as mock:
            mock.return_value = {"content": "ok", "input_tokens": 10, "output_tokens": 5}
            await client.generate(model, MESSAGES)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_to_google(self, client):
        model = _make_llm_model("google")
        with patch.object(client._providers["google"], "generate", new_callable=AsyncMock) as mock:
            mock.return_value = {"content": "ok", "input_tokens": 10, "output_tokens": 5}
            await client.generate(model, MESSAGES)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self, client):
        model = _make_llm_model("unknown_provider")
        with pytest.raises(ValueError, match="Unknown provider"):
            await client.generate(model, MESSAGES)


class TestStreamRouting:
    """generate_stream()이 각 provider의 stream()으로 올바르게 라우팅되는지 검증."""

    @pytest.mark.asyncio
    async def test_stream_routes_to_openai(self, client):
        model = _make_llm_model("openai")

        async def mock_stream(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"

        with patch.object(client._providers["openai"], "stream", side_effect=mock_stream):
            chunks = []
            async for chunk in client.generate_stream(model, MESSAGES):
                chunks.append(chunk)
            assert chunks == ["chunk1", "chunk2"]

    @pytest.mark.asyncio
    async def test_stream_routes_to_runpod(self, client):
        model = _make_llm_model("runpod")

        async def mock_stream(*args, **kwargs):
            yield "r1"

        with patch.object(client._providers["runpod"], "stream", side_effect=mock_stream):
            chunks = []
            async for chunk in client.generate_stream(model, MESSAGES):
                chunks.append(chunk)
            assert chunks == ["r1"]

    @pytest.mark.asyncio
    async def test_stream_routes_to_anthropic(self, client):
        model = _make_llm_model("anthropic")

        async def mock_stream(*args, **kwargs):
            yield "a1"

        with patch.object(client._providers["anthropic"], "stream", side_effect=mock_stream):
            chunks = []
            async for chunk in client.generate_stream(model, MESSAGES):
                chunks.append(chunk)
            assert chunks == ["a1"]

    @pytest.mark.asyncio
    async def test_stream_routes_to_google(self, client):
        model = _make_llm_model("google")

        async def mock_stream(*args, **kwargs):
            yield "g1"

        with patch.object(client._providers["google"], "stream", side_effect=mock_stream):
            chunks = []
            async for chunk in client.generate_stream(model, MESSAGES):
                chunks.append(chunk)
            assert chunks == ["g1"]
