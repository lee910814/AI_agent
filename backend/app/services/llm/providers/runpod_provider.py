"""RunPod Serverless (SGLang) provider 구현.

RunPod SGLang은 OpenAI-compatible API를 제공하므로
OpenAI SSE 파서를 재사용한다.
"""

import logging
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.services.llm.providers.base import APIKeyError, BaseProvider
from app.services.llm.providers.openai_provider import _iter_openai_sse

logger = logging.getLogger(__name__)

_RUNPOD_BASE_URL = "https://api.runpod.ai/v2/{endpoint_id}/openai/v1"


class RunPodProvider(BaseProvider):
    """RunPod Serverless SGLang provider.

    OpenAI-compatible 엔드포인트를 사용하므로 응답 파싱은 _iter_openai_sse를 재사용한다.
    HTTP 클라이언트는 외부에서 주입받아 InferenceClient의 커넥션 풀을 공유한다.
    """

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http

    def _get_http(self) -> httpx.AsyncClient:
        """공유 또는 폴백 HTTP 클라이언트를 반환한다.

        InferenceClient에서 주입받은 클라이언트가 없으면 새 AsyncClient를 생성한다.
        """
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    def _base_url(self) -> str:
        """설정의 runpod_endpoint_id를 이용해 RunPod API 기본 URL을 반환한다."""
        return _RUNPOD_BASE_URL.format(endpoint_id=settings.runpod_endpoint_id)

    async def generate(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        """플랫폼 RunPod API 키로 비스트리밍 호출한다.

        Args:
            model_id: SGLang에 배포된 모델 ID 문자열.
            messages: OpenAI 형식 메시지 목록.
            **kwargs: temperature, max_tokens 등 추가 파라미터.

        Returns:
            content, input_tokens, output_tokens, finish_reason 키를 포함하는 dict.

        Raises:
            APIKeyError: API 키가 유효하지 않은 경우 (401/403).
            httpx.HTTPStatusError: HTTP 요청 실패 시.
        """
        response = await self._get_http().post(
            f"{self._base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.runpod_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
            },
        )
        if response.status_code in (401, 403):
            raise APIKeyError(f"RunPod {response.status_code}: {response.text[:300]}")
        if not response.is_success:
            raise httpx.HTTPStatusError(
                f"RunPod API {response.status_code}: {response.text[:300]}",
                request=response.request, response=response,
            )
        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return {
            "content": choice["message"]["content"],
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "finish_reason": choice.get("finish_reason", "stop"),
        }

    async def generate_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """RunPod BYOK 호출 — 플랫폼 키로 위임한다.

        RunPod는 엔드포인트 ID가 플랫폼 수준에서 고정되므로 사용자 키 교체 시나리오가 없다.
        BaseProvider 인터페이스 준수를 위해 generate()로 위임한다.
        """
        # RunPod는 엔드포인트 ID가 플랫폼 수준에서 고정되므로 BYOK는 플랫폼 호출과 동일
        # api_key를 사용자 키로 교체하는 시나리오가 없어 generate()로 위임
        return await self.generate(model_id, messages, **kwargs)

    async def stream(
        self, model_id: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """플랫폼 RunPod API 키로 SSE 스트리밍 호출한다."""
        async with self._get_http().stream(
            "POST",
            f"{self._base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.runpod_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
                "stream": True,
                "stream_options": {"include_usage": True},
            },
        ) as response:
            if response.status_code in (401, 403):
                body_bytes = await response.aread()
                raise APIKeyError(f"RunPod {response.status_code}: {body_bytes.decode(errors='replace')[:300]}")
            if not response.is_success:
                body_bytes = await response.aread()
                raise httpx.HTTPStatusError(
                    f"RunPod API {response.status_code}: {body_bytes.decode(errors='replace')[:300]}",
                    request=response.request, response=response,
                )
            async for chunk in _iter_openai_sse(response, usage_out):
                yield chunk

    async def stream_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """RunPod BYOK 스트리밍 — 플랫폼 키 스트리밍으로 위임한다.

        RunPod는 BYOK 스트리밍도 플랫폼 키로 처리한다 (엔드포인트 ID 고정 구조).
        """
        # RunPod는 BYOK 스트리밍도 플랫폼 키로 처리
        async for chunk in self.stream(model_id, messages, usage_out, **kwargs):
            yield chunk
