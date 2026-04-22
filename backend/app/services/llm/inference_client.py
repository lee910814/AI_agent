import logging
import time
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.core.observability import create_generation, record_llm_metrics
from app.models.llm_model import LLMModel
from app.services.llm.providers import AnthropicProvider, GoogleProvider, OpenAIProvider, RunPodProvider
from app.services.llm.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class InferenceClient:
    """LLM 모델 라우터. provider별 분기 처리를 각 Provider 클래스에 위임.

    HTTP 연결 풀을 인스턴스 수준에서 공유해 매 LLM 호출마다 TCP/TLS 핸드셰이크를 생략.
    BYOK 스트리밍 호출 20개를 동시에 처리할 수 있는 커넥션 풀 설정.
    """

    def __init__(self) -> None:
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
        self._http = httpx.AsyncClient(timeout=120.0, limits=limits)

        # 공유 HTTP 클라이언트를 provider에 주입해 커넥션 풀을 재사용
        self._providers: dict[str, BaseProvider] = {
            "openai": OpenAIProvider(http=self._http),
            "anthropic": AnthropicProvider(http=self._http),
            "google": GoogleProvider(http=self._http),
            "runpod": RunPodProvider(http=self._http),
        }

    async def aclose(self) -> None:
        """HTTP 클라이언트 연결을 닫는다. 컨텍스트 매니저 종료 또는 명시적 정리 시 호출."""
        await self._http.aclose()

    async def __aenter__(self) -> "InferenceClient":
        """비동기 컨텍스트 매니저 진입."""
        return self

    async def __aexit__(self, *_: object) -> None:
        """비동기 컨텍스트 매니저 종료 — HTTP 클라이언트를 닫는다."""
        await self.aclose()

    # ── 퍼블릭 인터페이스 ──

    async def generate(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """provider에 따라 적절한 API로 라우팅하여 LLM 비스트리밍 응답을 반환한다.

        Langfuse 트레이스 기록과 Prometheus 메트릭 계측을 수행한다.

        Args:
            model: llm_models 테이블에서 조회한 LLMModel 인스턴스.
            messages: OpenAI 형식 메시지 목록 [{"role": "...", "content": "..."}].
            **kwargs: 모델별 추가 파라미터 (temperature, max_tokens 등).

        Returns:
            content, input_tokens, output_tokens, finish_reason 키를 포함하는 dict.

        Raises:
            ValueError: 등록되지 않은 provider인 경우.
            APIKeyError: API 키가 유효하지 않은 경우 (401/403).
            httpx.HTTPStatusError: HTTP 요청 실패 시.
        """
        generation = create_generation(
            name=f"llm_{model.provider}",
            model=model.model_id,
            input_messages=messages,
        )

        start = time.monotonic()
        try:
            result = await self._route_generate(model, messages, **kwargs)
            duration = time.monotonic() - start

            if generation:
                generation.end(
                    output=result["content"],
                    usage={
                        "input": result.get("input_tokens", 0),
                        "output": result.get("output_tokens", 0),
                    },
                )

            record_llm_metrics(
                provider=model.provider,
                model=model.model_id,
                duration=duration,
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
            )

            return result
        except Exception as exc:
            if generation:
                generation.end(status_message=str(exc), level="ERROR")
            raise

    async def generate_stream(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """provider에 따라 SSE 스트리밍 응답을 생성한다.

        Args:
            model: llm_models 테이블에서 조회한 LLMModel 인스턴스.
            messages: OpenAI 형식 메시지 목록.
            usage_out: 완료 후 input_tokens/output_tokens를 기록할 dict. None이면 내부 생성.
            **kwargs: 모델별 추가 파라미터 (temperature, max_tokens 등).

        Yields:
            스트리밍 텍스트 청크 문자열.
        """
        if usage_out is None:
            usage_out = {}
        async for chunk in self._route_stream(model, messages, usage_out, **kwargs):
            yield chunk

    async def generate_byok(
        self, provider: str, model_id: str, api_key: str, messages: list[dict], **kwargs
    ) -> dict:
        """사용자 제공 API 키(BYOK)로 LLM을 비스트리밍 호출한다. 토론 엔진 전용.

        Args:
            provider: LLM provider 이름 ("openai", "anthropic", "google", "runpod").
            model_id: 사용할 모델 ID 문자열 (예: "gpt-4o-mini").
            api_key: 사용자가 제공한 API 키.
            messages: OpenAI 형식 메시지 목록.
            **kwargs: 모델별 추가 파라미터.

        Returns:
            content, input_tokens, output_tokens, finish_reason 키를 포함하는 dict.

        Raises:
            ValueError: 지원하지 않는 provider인 경우.
            APIKeyError: API 키가 유효하지 않은 경우.
        """
        p = self._providers.get(provider)
        if p is None:
            raise ValueError(f"BYOK not supported for provider: {provider}")
        return await p.generate_byok(model_id, api_key, messages, **kwargs)

    async def generate_stream_byok(
        self,
        provider: str,
        model_id: str,
        api_key: str,
        messages: list[dict],
        usage_out: dict | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """사용자 제공 API 키(BYOK)로 SSE 스트리밍 호출한다. 토론 엔진 실시간 출력 전용.

        Args:
            provider: LLM provider 이름 ("openai", "anthropic", "google", "runpod").
            model_id: 사용할 모델 ID 문자열.
            api_key: 사용자가 제공한 API 키.
            messages: OpenAI 형식 메시지 목록.
            usage_out: 완료 후 토큰 수를 기록할 dict. None이면 내부 생성.
            **kwargs: 모델별 추가 파라미터.

        Yields:
            스트리밍 텍스트 청크 문자열.

        Raises:
            ValueError: 지원하지 않는 provider인 경우.
        """
        if usage_out is None:
            usage_out = {}
        p = self._providers.get(provider)
        if p is None:
            raise ValueError(f"BYOK streaming not supported for provider: {provider}")
        async for chunk in p.stream_byok(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    # ── 내부 라우팅 ──

    async def _route_generate(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """model.provider를 기반으로 적절한 provider의 generate()를 호출한다."""
        p = self._providers.get(model.provider)
        if p is None:
            raise ValueError(f"Unknown provider: {model.provider}")
        return await p.generate(model.model_id, messages, **kwargs)

    async def _route_stream(
        self, model: LLMModel, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """model.provider를 기반으로 적절한 provider의 stream()을 호출한다."""
        p = self._providers.get(model.provider)
        if p is None:
            raise ValueError(f"Unknown provider: {model.provider}")
        async for chunk in p.stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    # ── 하위 호환 위임 메서드 ──
    # debate_orchestrator.py 등 기존 코드가 직접 참조하는 메서드를 유지.

    async def _call_openai(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """OpenAI provider 비스트리밍 호출 위임 메서드 (하위 호환용)."""
        return await self._providers["openai"].generate(model.model_id, messages, **kwargs)

    async def _call_openai_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """OpenAI BYOK 비스트리밍 호출 위임 메서드 (하위 호환용)."""
        return await self._providers["openai"].generate_byok(model_id, api_key, messages, **kwargs)

    async def _call_anthropic(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """Anthropic provider 비스트리밍 호출 위임 메서드 (하위 호환용)."""
        return await self._providers["anthropic"].generate(model.model_id, messages, **kwargs)

    async def _call_anthropic_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """Anthropic BYOK 비스트리밍 호출 위임 메서드 (하위 호환용)."""
        return await self._providers["anthropic"].generate_byok(model_id, api_key, messages, **kwargs)

    async def _call_google(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """Google provider 비스트리밍 호출 위임 메서드 (하위 호환용)."""
        return await self._providers["google"].generate(model.model_id, messages, **kwargs)

    async def _call_google_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """Google BYOK 비스트리밍 호출 위임 메서드 (하위 호환용)."""
        return await self._providers["google"].generate_byok(model_id, api_key, messages, **kwargs)

    async def _call_runpod(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """RunPod provider 비스트리밍 호출 위임 메서드 (하위 호환용)."""
        return await self._providers["runpod"].generate(model.model_id, messages, **kwargs)

    async def _stream_openai(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """OpenAI provider SSE 스트리밍 호출 위임 메서드 (하위 호환용)."""
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["openai"].stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_openai_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """OpenAI BYOK SSE 스트리밍 호출 위임 메서드 (하위 호환용)."""
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["openai"].stream_byok(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_anthropic(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Anthropic provider SSE 스트리밍 호출 위임 메서드 (하위 호환용)."""
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["anthropic"].stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_anthropic_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Anthropic BYOK SSE 스트리밍 호출 위임 메서드 (하위 호환용)."""
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["anthropic"].stream_byok(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_google(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Google provider SSE 스트리밍 호출 위임 메서드 (하위 호환용)."""
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["google"].stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_google_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Google BYOK SSE 스트리밍 호출 위임 메서드 (하위 호환용)."""
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["google"].stream_byok(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_runpod(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """RunPod provider SSE 스트리밍 호출 위임 메서드 (하위 호환용)."""
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["runpod"].stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    # ── 유틸리티 (기존 테스트 및 외부 코드가 참조) ──

    @staticmethod
    def _split_system_messages(messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI 형식 messages에서 system 메시지를 분리한다 (하위 호환용).

        내부적으로 AnthropicProvider._split_system_messages()에 위임한다.
        """
        from app.services.llm.providers.anthropic_provider import AnthropicProvider  # 순환 import 방지용 지연 import

        return AnthropicProvider._split_system_messages(messages)

    @staticmethod
    def _to_gemini_format(messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI 형식 messages를 Gemini contents 형식으로 변환한다 (하위 호환용).

        내부적으로 GoogleProvider._to_gemini_format()에 위임한다.
        """
        from app.services.llm.providers.google_provider import GoogleProvider  # 순환 import 방지용 지연 import

        return GoogleProvider._to_gemini_format(messages)

    @staticmethod
    async def _iter_openai_sse(response: "httpx.Response", usage_out: dict) -> AsyncGenerator[str, None]:
        """OpenAI-compatible SSE 스트림 파서 위임 메서드 (하위 호환용)."""
        from app.services.llm.providers.openai_provider import _iter_openai_sse  # 순환 import 방지용 지연 import

        async for chunk in _iter_openai_sse(response, usage_out):
            yield chunk

    @staticmethod
    async def _iter_anthropic_sse(response: "httpx.Response", usage_out: dict) -> AsyncGenerator[str, None]:
        """Anthropic SSE 스트림 파서 위임 메서드 (하위 호환용)."""
        from app.services.llm.providers.anthropic_provider import _iter_anthropic_sse  # 순환 import 방지용 지연 import

        async for chunk in _iter_anthropic_sse(response, usage_out):
            yield chunk

    @staticmethod
    async def _iter_google_sse(response: "httpx.Response", usage_out: dict) -> AsyncGenerator[str, None]:
        """Google Gemini SSE 스트림 파서 위임 메서드 (하위 호환용)."""
        from app.services.llm.providers.google_provider import _iter_google_sse  # 순환 import 방지용 지연 import

        async for chunk in _iter_google_sse(response, usage_out):
            yield chunk
