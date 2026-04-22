"""Provider 추상화 계층 단위 테스트.

TDD Red-Green 순서:
1. 이 파일을 먼저 작성 (Red — 아직 providers 패키지 없음)
2. providers/ 구현 후 Green 확인
"""

import pytest
from app.services.llm.providers.base import BaseProvider
from app.services.llm.providers import OpenAIProvider, AnthropicProvider, GoogleProvider, RunPodProvider


class TestProviderHierarchy:
    def test_all_providers_extend_base(self):
        """모든 provider가 BaseProvider를 상속한다."""
        for cls in [OpenAIProvider, AnthropicProvider, GoogleProvider, RunPodProvider]:
            assert issubclass(cls, BaseProvider), f"{cls.__name__} must extend BaseProvider"

    def test_openai_provider_instantiable(self):
        """OpenAIProvider를 인자 없이 생성할 수 있다."""
        provider = OpenAIProvider()
        assert provider is not None

    def test_anthropic_provider_instantiable(self):
        """AnthropicProvider를 인자 없이 생성할 수 있다."""
        provider = AnthropicProvider()
        assert provider is not None

    def test_google_provider_instantiable(self):
        """GoogleProvider를 인자 없이 생성할 수 있다."""
        provider = GoogleProvider()
        assert provider is not None

    def test_runpod_provider_instantiable(self):
        """RunPodProvider를 인자 없이 생성할 수 있다."""
        provider = RunPodProvider()
        assert provider is not None


class TestBaseProviderInterface:
    def test_base_provider_is_abstract(self):
        """BaseProvider는 직접 인스턴스화할 수 없다."""
        with pytest.raises(TypeError):
            BaseProvider()  # type: ignore[abstract]

    def test_all_providers_have_generate(self):
        """모든 provider 클래스가 generate 메서드를 보유한다."""
        for cls in [OpenAIProvider, AnthropicProvider, GoogleProvider, RunPodProvider]:
            assert hasattr(cls, "generate"), f"{cls.__name__} missing generate()"
            assert callable(getattr(cls, "generate"))

    def test_all_providers_have_generate_byok(self):
        """모든 provider 클래스가 generate_byok 메서드를 보유한다."""
        for cls in [OpenAIProvider, AnthropicProvider, GoogleProvider, RunPodProvider]:
            assert hasattr(cls, "generate_byok"), f"{cls.__name__} missing generate_byok()"
            assert callable(getattr(cls, "generate_byok"))

    def test_all_providers_have_stream(self):
        """모든 provider 클래스가 stream 메서드를 보유한다."""
        for cls in [OpenAIProvider, AnthropicProvider, GoogleProvider, RunPodProvider]:
            assert hasattr(cls, "stream"), f"{cls.__name__} missing stream()"
            assert callable(getattr(cls, "stream"))

    def test_all_providers_have_stream_byok(self):
        """모든 provider 클래스가 stream_byok 메서드를 보유한다."""
        for cls in [OpenAIProvider, AnthropicProvider, GoogleProvider, RunPodProvider]:
            assert hasattr(cls, "stream_byok"), f"{cls.__name__} missing stream_byok()"
            assert callable(getattr(cls, "stream_byok"))


class TestInferenceClientWithProviders:
    def test_inference_client_has_all_providers(self):
        """InferenceClient가 4개 provider를 모두 보유한다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()
        for p in ["openai", "anthropic", "google", "runpod"]:
            assert p in client._providers, f"_providers missing '{p}'"
            assert isinstance(client._providers[p], BaseProvider)

    def test_inference_client_backward_compat_openai_byok(self):
        """기존 _call_openai_byok 메서드가 존재하고 호출 가능하다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()
        assert hasattr(client, "_call_openai_byok")
        assert callable(client._call_openai_byok)

    def test_inference_client_backward_compat_call_openai(self):
        """기존 _call_openai 위임 메서드가 존재한다 (generate 내부 라우팅 경로)."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()
        assert hasattr(client, "_call_openai")

    def test_inference_client_backward_compat_call_anthropic(self):
        """기존 _call_anthropic 위임 메서드가 존재한다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()
        assert hasattr(client, "_call_anthropic")

    def test_inference_client_backward_compat_call_runpod(self):
        """기존 _call_runpod 위임 메서드가 존재한다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()
        assert hasattr(client, "_call_runpod")

    def test_inference_client_backward_compat_call_google(self):
        """기존 _call_google 위임 메서드가 존재한다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()
        assert hasattr(client, "_call_google")

    def test_inference_client_backward_compat_stream_openai(self):
        """기존 _stream_openai 위임 메서드가 존재한다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()
        assert hasattr(client, "_stream_openai")

    def test_inference_client_backward_compat_stream_openai_byok(self):
        """기존 _stream_openai_byok 위임 메서드가 존재한다."""
        from app.services.llm.inference_client import InferenceClient

        client = InferenceClient()
        assert hasattr(client, "_stream_openai_byok")


class TestOpenAIProviderHelpers:
    def test_max_tokens_key_standard_model(self):
        """일반 모델은 max_tokens 키를 반환한다."""
        from app.services.llm.providers.openai_provider import openai_max_tokens_key

        assert openai_max_tokens_key("gpt-4o") == "max_tokens"
        assert openai_max_tokens_key("gpt-3.5-turbo") == "max_tokens"

    def test_max_tokens_key_completion_model(self):
        """o-series 및 gpt-4.1+는 max_completion_tokens 키를 반환한다."""
        from app.services.llm.providers.openai_provider import openai_max_tokens_key

        assert openai_max_tokens_key("o1-mini") == "max_completion_tokens"
        assert openai_max_tokens_key("o3") == "max_completion_tokens"
        assert openai_max_tokens_key("gpt-4.1") == "max_completion_tokens"
        assert openai_max_tokens_key("gpt-5-nano") == "max_completion_tokens"

    def test_supports_temperature_standard_model(self):
        """일반 모델은 temperature를 지원한다."""
        from app.services.llm.providers.openai_provider import openai_supports_temperature

        assert openai_supports_temperature("gpt-4o") is True
        assert openai_supports_temperature("gpt-4.1") is True

    def test_no_temperature_o_series(self):
        """o-series 및 gpt-5 계열은 temperature를 지원하지 않는다."""
        from app.services.llm.providers.openai_provider import openai_supports_temperature

        assert openai_supports_temperature("o1") is False
        assert openai_supports_temperature("o3-mini") is False
        assert openai_supports_temperature("gpt-5-nano") is False


class TestProviderStaticHelpers:
    def test_split_system_messages_preserved(self):
        """AnthropicProvider의 _split_system_messages가 기존 동작을 그대로 유지한다."""
        from app.services.llm.providers.anthropic_provider import AnthropicProvider

        msgs = [
            {"role": "system", "content": "Rule A"},
            {"role": "system", "content": "Rule B"},
            {"role": "user", "content": "Hello"},
        ]
        system, api_msgs = AnthropicProvider._split_system_messages(msgs)
        assert "Rule A" in system
        assert "Rule B" in system
        assert len(api_msgs) == 1
        assert api_msgs[0]["role"] == "user"

    def test_to_gemini_format_preserved(self):
        """GoogleProvider의 _to_gemini_format이 기존 동작을 그대로 유지한다."""
        from app.services.llm.providers.google_provider import GoogleProvider

        msgs = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        system, contents = GoogleProvider._to_gemini_format(msgs)
        assert "System" in system
        assert len(contents) == 2
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"
