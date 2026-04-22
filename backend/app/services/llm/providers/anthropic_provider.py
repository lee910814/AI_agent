"""Anthropic provider 구현."""

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.services.llm.providers.base import APIKeyError, BaseProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic Messages API provider.

    HTTP 클라이언트는 외부에서 주입받아 InferenceClient의 커넥션 풀을 공유한다.
    system 메시지를 OpenAI 형식에서 분리하여 Anthropic API 규격으로 변환한다.
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

    async def generate(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        """플랫폼 Anthropic API 키로 비스트리밍 호출한다."""
        return await self._call_impl(model_id, settings.anthropic_api_key, messages, **kwargs)

    async def generate_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """사용자 제공 Anthropic API 키(BYOK)로 비스트리밍 호출한다."""
        return await self._call_impl(model_id, api_key, messages, **kwargs)

    async def stream(
        self, model_id: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """플랫폼 Anthropic API 키로 SSE 스트리밍 호출한다."""
        async for chunk in self._stream_impl(model_id, settings.anthropic_api_key, messages, usage_out, **kwargs):
            yield chunk

    async def stream_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """사용자 제공 Anthropic API 키(BYOK)로 SSE 스트리밍 호출한다."""
        async for chunk in self._stream_impl(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _call_impl(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """Anthropic Messages API 비스트리밍 호출 구현 (플랫폼/BYOK 공통).

        Args:
            model_id: Anthropic 모델 ID 문자열 (예: "claude-3-5-haiku-20241022").
            api_key: 플랫폼 키 또는 사용자 BYOK 키.
            messages: OpenAI 형식 메시지 목록 (system 메시지 포함 가능).
            **kwargs: temperature, max_tokens 등 추가 파라미터.

        Returns:
            content, input_tokens, output_tokens, finish_reason 키를 포함하는 dict.

        Raises:
            APIKeyError: API 키가 유효하지 않은 경우 (401/403).
            httpx.HTTPStatusError: HTTP 요청 실패 시.
        """
        system_prompt, api_messages = self._split_system_messages(messages)
        body: dict = {
            "model": model_id,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
        }
        if system_prompt:
            body["system"] = system_prompt
        if "tools" in kwargs:
            body["tools"] = kwargs["tools"]
        if "tool_choice" in kwargs:
            tc = kwargs["tool_choice"]
            body["tool_choice"] = {"type": tc} if isinstance(tc, str) else tc
        response = await self._get_http().post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if response.status_code in (401, 403):
            raise APIKeyError(f"Anthropic {response.status_code}: {response.text[:300]}")
        if not response.is_success:
            raise httpx.HTTPStatusError(
                f"Anthropic API {response.status_code}: {response.text[:300]}",
                request=response.request, response=response,
            )
        data = response.json()
        content_blocks = data.get("content", [])
        text_blocks = [b["text"] for b in content_blocks if b.get("type") == "text"]
        content_text = "".join(text_blocks)
        tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]
        result = {
            "content": content_text,
            "input_tokens": data["usage"]["input_tokens"],
            "output_tokens": data["usage"]["output_tokens"],
            "finish_reason": data.get("stop_reason", "end_turn"),
        }
        if tool_use_blocks:
            result["tool_calls"] = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                }
                for b in tool_use_blocks
            ]
        return result

    async def _stream_impl(
        self,
        model_id: str,
        api_key: str,
        messages: list[dict],
        usage_out: dict,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Anthropic Messages API SSE 스트리밍 구현 (플랫폼/BYOK 공통).

        message_start 이벤트에서 input_tokens, message_delta 이벤트에서 output_tokens를 캡처한다.

        Args:
            model_id: Anthropic 모델 ID 문자열.
            api_key: 플랫폼 키 또는 사용자 BYOK 키.
            messages: OpenAI 형식 메시지 목록.
            usage_out: 스트리밍 완료 후 토큰 수를 기록할 dict.
            **kwargs: temperature, max_tokens 등 추가 파라미터.

        Yields:
            스트리밍 텍스트 청크 문자열.

        Raises:
            APIKeyError: API 키가 유효하지 않은 경우 (401/403).
            httpx.HTTPStatusError: HTTP 요청 실패 시.
        """
        system_prompt, api_messages = self._split_system_messages(messages)
        body: dict = {
            "model": model_id,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
            "stream": True,
        }
        if system_prompt:
            body["system"] = system_prompt
        if "tools" in kwargs:
            body["tools"] = kwargs["tools"]
        async with self._get_http().stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body,
        ) as response:
            if response.status_code in (401, 403):
                body_bytes = await response.aread()
                raise APIKeyError(f"Anthropic {response.status_code}: {body_bytes.decode(errors='replace')[:300]}")
            if not response.is_success:
                body_bytes = await response.aread()
                raise httpx.HTTPStatusError(
                    f"Anthropic API {response.status_code}: {body_bytes.decode(errors='replace')[:300]}",
                    request=response.request, response=response,
                )
            async for chunk in _iter_anthropic_sse(response, usage_out):
                yield chunk

    @staticmethod
    def _split_system_messages(messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI 형식 messages에서 system 메시지를 분리하고,
        tool_calls/tool role 메시지를 Anthropic 네이티브 형식으로 변환한다."""
        system_parts = []
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "assistant" and msg.get("tool_calls"):
                # OpenAI assistant+tool_calls → Anthropic assistant+tool_use content blocks
                content_blocks = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"]),
                    })
                api_messages.append({"role": "assistant", "content": content_blocks})
            elif msg["role"] == "tool":
                # OpenAI tool role → Anthropic user+tool_result content block
                api_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg["tool_call_id"],
                        "content": msg["content"],
                    }],
                })
            else:
                api_messages.append({"role": msg["role"], "content": msg["content"]})
        return "\n\n".join(system_parts), api_messages


async def _iter_anthropic_sse(
    response: httpx.Response, usage_out: dict
) -> AsyncGenerator[str, None]:
    """Anthropic Messages API SSE 스트림을 파싱하여 텍스트 청크를 생성한다.

    message_start 이벤트에서 input_tokens, message_delta 이벤트에서 output_tokens를 캡처한다.
    max_tokens stop_reason은 OpenAI 규격 "length"로 정규화한다.

    Args:
        response: httpx 스트리밍 응답 객체.
        usage_out: 완료 후 토큰 수와 finish_reason을 기록할 dict.

    Yields:
        content_block_delta 이벤트의 text_delta 문자열.
    """
    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if event_type == "message_start":
            usage_out["input_tokens"] = event.get("message", {}).get("usage", {}).get("input_tokens", 0)
        elif event_type == "message_delta":
            usage_out["output_tokens"] = event.get("usage", {}).get("output_tokens", 0)
            # Anthropic: max_tokens → OpenAI 규격 "length"로 정규화
            stop_reason = event.get("delta", {}).get("stop_reason")
            if stop_reason:
                usage_out["finish_reason"] = "length" if stop_reason == "max_tokens" else stop_reason
        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                yield delta["text"]
        elif event_type == "message_stop":
            break
