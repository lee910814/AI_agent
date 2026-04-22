"""LLM 공통 유틸리티 — provider 추론 등 여러 서비스에서 공유."""

import logging

logger = logging.getLogger(__name__)

# RunPod 커스텀 엔드포인트 모델 식별 접두사 (SGLang 호환 OpenAI-like API).
# 동일 이름의 외부 직접 API가 추가될 경우 provider 필드 기반 관리로 전환 필요.
_RUNPOD_PREFIXES = ("meta-", "llama", "mistral", "qwen")


def infer_provider(model_id: str) -> str:
    """model_id에서 LLM provider를 추론한다.

    빈 model_id 또는 알 수 없는 모델은 'openai' fallback + WARNING 로그.
    """
    model = (model_id or "").strip().lower()
    if not model:
        logger.warning("infer_provider: 빈 model_id, openai로 기본 설정")
        return "openai"
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("gemini-"):
        return "google"
    if any(model.startswith(p) for p in _RUNPOD_PREFIXES):
        return "runpod"
    logger.debug("infer_provider: 알 수 없는 model_id=%s, openai로 기본 설정", model_id)
    return "openai"
