"""LLM provider 추상 기반 클래스."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class APIKeyError(Exception):
    """API 키 인증 실패(401/403) 예외.

    HTTP 401/403 응답 수신 시 발생하며, 재시도 없이 즉시 부전패 처리된다.
    """


class BaseProvider(ABC):
    """LLM provider 추상 기반 클래스.

    모든 provider는 이 클래스를 상속하고 4개의 추상 메서드를 구현해야 한다.
    플랫폼 API 키 호출(generate/stream)과 BYOK 호출(generate_byok/stream_byok)을 분리한다.
    """

    @abstractmethod
    async def generate(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        """플랫폼 API 키로 LLM 비스트리밍 호출한다.

        Args:
            model_id: 사용할 모델 ID 문자열 (예: "gpt-4o-mini", "claude-3-5-haiku-20241022").
            messages: OpenAI 형식 메시지 목록 [{"role": "...", "content": "..."}].
            **kwargs: 모델별 추가 파라미터 (temperature, max_tokens 등).

        Returns:
            content, input_tokens, output_tokens, finish_reason 키를 포함하는 dict.

        Raises:
            APIKeyError: 플랫폼 API 키가 유효하지 않은 경우 (401/403).
            httpx.HTTPStatusError: HTTP 요청 실패 시.
        """
        ...

    @abstractmethod
    async def generate_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """사용자 제공 API 키(BYOK)로 LLM 비스트리밍 호출한다.

        Args:
            model_id: 사용할 모델 ID 문자열.
            api_key: 사용자가 제공한 API 키.
            messages: OpenAI 형식 메시지 목록.
            **kwargs: 모델별 추가 파라미터.

        Returns:
            content, input_tokens, output_tokens, finish_reason 키를 포함하는 dict.

        Raises:
            APIKeyError: 사용자 API 키가 유효하지 않은 경우 (401/403).
            httpx.HTTPStatusError: HTTP 요청 실패 시.
        """
        ...

    @abstractmethod
    async def stream(
        self, model_id: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """플랫폼 API 키로 SSE 스트리밍 호출한다.

        Args:
            model_id: 사용할 모델 ID 문자열.
            messages: OpenAI 형식 메시지 목록.
            usage_out: 스트리밍 완료 후 input_tokens/output_tokens를 기록할 dict.
            **kwargs: 모델별 추가 파라미터.

        Yields:
            스트리밍 텍스트 청크 문자열.
        """
        ...

    @abstractmethod
    async def stream_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """사용자 제공 API 키(BYOK)로 SSE 스트리밍 호출한다.

        Args:
            model_id: 사용할 모델 ID 문자열.
            api_key: 사용자가 제공한 API 키.
            messages: OpenAI 형식 메시지 목록.
            usage_out: 스트리밍 완료 후 input_tokens/output_tokens를 기록할 dict.
            **kwargs: 모델별 추가 파라미터.

        Yields:
            스트리밍 텍스트 청크 문자열.
        """
        ...
