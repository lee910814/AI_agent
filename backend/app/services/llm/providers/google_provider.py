"""Google Gemini provider 구현."""

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.services.llm.providers.base import APIKeyError, BaseProvider

logger = logging.getLogger(__name__)


class GoogleProvider(BaseProvider):
    """Google Gemini API provider.

    API 키를 URL 파라미터 대신 x-goog-api-key 헤더로 전달하여 로그/트레이스에 키 노출을 방지한다.
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

    async def generate(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        """플랫폼 Google API 키로 비스트리밍 호출한다."""
        return await self._call_impl(model_id, settings.google_api_key, messages, **kwargs)

    async def generate_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """사용자 제공 Google API 키(BYOK)로 비스트리밍 호출한다."""
        return await self._call_impl(model_id, api_key, messages, **kwargs)

    async def stream(
        self, model_id: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """플랫폼 Google API 키로 SSE 스트리밍 호출한다."""
        async for chunk in self._stream_impl(model_id, settings.google_api_key, messages, usage_out, **kwargs):
            yield chunk

    async def stream_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """사용자 제공 Google API 키(BYOK)로 SSE 스트리밍 호출한다."""
        async for chunk in self._stream_impl(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _call_impl(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """Google Gemini API 비스트리밍 호출 구현 (플랫폼/BYOK 공통).

        Args:
            model_id: Gemini 모델 ID 문자열 (예: "gemini-2.0-flash").
            api_key: 플랫폼 키 또는 사용자 BYOK 키.
            messages: OpenAI 형식 메시지 목록 (system 메시지 포함 가능).
            **kwargs: temperature, max_tokens 등 추가 파라미터.

        Returns:
            content, input_tokens, output_tokens, finish_reason 키를 포함하는 dict.

        Raises:
            APIKeyError: API 키가 유효하지 않은 경우 (401/403).
            httpx.HTTPStatusError: HTTP 요청 실패 시.
        """
        system_prompt, gemini_contents = self._to_gemini_format(messages)
        body: dict = {
            "contents": gemini_contents,
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if "tools" in kwargs:
            body["tools"] = kwargs["tools"]
        response = await self._get_http().post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json=body,
        )
        if response.status_code in (401, 403):
            raise APIKeyError(f"Google {response.status_code}: {response.text[:300]}")
        if not response.is_success:
            raise httpx.HTTPStatusError(
                f"Google API {response.status_code}: {response.text[:300]}",
                request=response.request, response=response,
            )
        data = response.json()
        candidate = data["candidates"][0]
        parts = candidate["content"]["parts"]
        func_calls = [p for p in parts if "functionCall" in p]
        text_parts = [p["text"] for p in parts if "text" in p]
        content_text = "".join(text_parts)
        usage_meta = data.get("usageMetadata", {})
        result = {
            "content": content_text,
            "input_tokens": usage_meta.get("promptTokenCount", 0),
            "output_tokens": usage_meta.get("candidatesTokenCount", 0),
            "finish_reason": candidate.get("finishReason", "STOP"),
        }
        if func_calls:
            result["tool_calls"] = [
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": fc["functionCall"]["name"],
                        "arguments": json.dumps(fc["functionCall"]["args"]),
                    },
                }
                for i, fc in enumerate(func_calls)
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
        """Google Gemini API SSE 스트리밍 구현 (플랫폼/BYOK 공통).

        usageMetadata 필드(마지막 청크)에서 promptTokenCount/candidatesTokenCount를 캡처한다.

        Args:
            model_id: Gemini 모델 ID 문자열.
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
        system_prompt, gemini_contents = self._to_gemini_format(messages)
        body: dict = {
            "contents": gemini_contents,
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if "tools" in kwargs:
            body["tools"] = kwargs["tools"]
        async with self._get_http().stream(
            "POST",
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:streamGenerateContent",
            params={"alt": "sse"},
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json=body,
        ) as response:
            if response.status_code in (401, 403):
                body_bytes = await response.aread()
                raise APIKeyError(f"Google {response.status_code}: {body_bytes.decode(errors='replace')[:300]}")
            if not response.is_success:
                body_bytes = await response.aread()
                raise httpx.HTTPStatusError(
                    f"Google API {response.status_code}: {body_bytes.decode(errors='replace')[:300]}",
                    request=response.request, response=response,
                )
            async for chunk in _iter_google_sse(response, usage_out):
                yield chunk

    @staticmethod
    def _to_gemini_format(messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI 형식 messages를 Gemini contents 형식으로 변환한다.
        tool_calls/tool role 메시지를 Gemini 네이티브 형식으로 변환한다."""
        system_parts = []
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "assistant" and msg.get("tool_calls"):
                # OpenAI assistant+tool_calls → Gemini model+functionCall parts
                parts = []
                if msg.get("content"):
                    parts.append({"text": msg["content"]})
                for tc in msg["tool_calls"]:
                    parts.append({
                        "functionCall": {
                            "name": tc["function"]["name"],
                            "args": json.loads(tc["function"]["arguments"]),
                        }
                    })
                contents.append({"role": "model", "parts": parts})
            elif msg["role"] == "tool":
                # OpenAI tool role → Gemini user+functionResponse part
                contents.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": "web_search",
                            "response": {"content": msg["content"]},
                        }
                    }],
                })
            elif msg["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
            else:
                contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
        return "\n\n".join(system_parts), contents


async def _iter_google_sse(
    response: httpx.Response, usage_out: dict
) -> AsyncGenerator[str, None]:
    """Google Gemini SSE 스트림을 파싱하여 텍스트 청크를 생성한다.

    usageMetadata 필드(마지막 청크)에서 promptTokenCount/candidatesTokenCount를 캡처한다.
    finishReason MAX_TOKENS는 OpenAI 규격 "length"로 정규화한다.

    Args:
        response: httpx 스트리밍 응답 객체.
        usage_out: 완료 후 토큰 수와 finish_reason을 기록할 dict.

    Yields:
        candidates[0].content.parts[].text 문자열 청크.
    """
    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        try:
            chunk = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if chunk.get("usageMetadata"):
            meta = chunk["usageMetadata"]
            usage_out["input_tokens"] = meta.get("promptTokenCount", 0)
            usage_out["output_tokens"] = meta.get("candidatesTokenCount", 0)
        candidates = chunk.get("candidates", [])
        if not candidates:
            continue
        # Google: MAX_TOKENS → OpenAI 규격 "length"로 정규화
        finish_reason = candidates[0].get("finishReason", "")
        if finish_reason:
            usage_out["finish_reason"] = "length" if finish_reason == "MAX_TOKENS" else finish_reason.lower()
        for part in candidates[0].get("content", {}).get("parts", []):
            if "text" in part:
                yield part["text"]
