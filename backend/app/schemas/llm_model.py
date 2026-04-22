from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LLMModelCreate(BaseModel):
    """LLM 모델 등록 요청 스키마.

    관리자가 새 LLM 모델을 시스템에 등록할 때 전달하는 데이터.

    Attributes:
        provider: LLM 공급자 식별자 ('openai', 'anthropic', 'google', 'runpod').
        model_id: 공급자 API에서 사용하는 모델 식별자 (예: 'gpt-4.1').
        display_name: UI에 표시할 사람 친화적 이름.
        input_cost_per_1m: 입력 토큰 100만 개당 USD 비용.
        output_cost_per_1m: 출력 토큰 100만 개당 USD 비용.
        max_context_length: 모델이 지원하는 최대 컨텍스트 토큰 수.
        is_adult_only: 성인 전용 콘텐츠 허용 여부.
        tier: 모델 등급 ('economy', 'standard', 'premium').
        credit_per_1k_tokens: 1,000 토큰당 차감할 플랫폼 크레딧 수.
        metadata: 추가 메타데이터 (선택).
    """

    provider: str
    model_id: str
    display_name: str
    input_cost_per_1m: float
    output_cost_per_1m: float
    max_context_length: int
    is_adult_only: bool = False
    tier: str = "economy"
    credit_per_1k_tokens: int = 1
    metadata: dict | None = None


class LLMModelUpdate(BaseModel):
    """LLM 모델 수정 요청 스키마.

    관리자가 기존 LLM 모델 정보를 부분 수정할 때 사용하는 스키마.
    모든 필드는 선택적이며, 전달된 필드만 업데이트된다.

    Attributes:
        display_name: 변경할 표시 이름.
        input_cost_per_1m: 변경할 입력 토큰 비용 (USD/1M).
        output_cost_per_1m: 변경할 출력 토큰 비용 (USD/1M).
        max_context_length: 변경할 최대 컨텍스트 길이.
        is_adult_only: 성인 전용 여부 변경.
        is_active: 모델 활성화/비활성화 여부.
        tier: 변경할 모델 등급.
        credit_per_1k_tokens: 변경할 크레딧 차감 단가.
        metadata: 변경할 추가 메타데이터.
    """

    display_name: str | None = None
    input_cost_per_1m: float | None = None
    output_cost_per_1m: float | None = None
    max_context_length: int | None = None
    is_adult_only: bool | None = None
    is_active: bool | None = None
    tier: str | None = None
    credit_per_1k_tokens: int | None = None
    metadata: dict | None = None


class LLMModelResponse(BaseModel):
    """LLM 모델 조회 응답 스키마.

    클라이언트에 반환되는 LLM 모델 정보.

    Attributes:
        id: 모델 UUID.
        provider: LLM 공급자.
        model_id: 공급자 API 모델 식별자.
        display_name: UI 표시 이름.
        input_cost_per_1m: 입력 토큰 비용 (USD/1M).
        output_cost_per_1m: 출력 토큰 비용 (USD/1M).
        max_context_length: 최대 컨텍스트 토큰 수.
        is_adult_only: 성인 전용 여부.
        is_active: 현재 활성화 상태.
        tier: 모델 등급.
        credit_per_1k_tokens: 1,000 토큰당 크레딧 차감량.
        created_at: 등록 일시.
    """

    id: UUID
    provider: str
    model_id: str
    display_name: str
    input_cost_per_1m: float
    output_cost_per_1m: float
    max_context_length: int
    is_adult_only: bool
    is_active: bool
    tier: str
    credit_per_1k_tokens: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LLMModelStatsResponse(BaseModel):
    """LLM 모델별 사용 통계 응답 스키마.

    각 모델을 사용하는 에이전트 수와 해당 에이전트들의 누적 전적·승률을 포함한다.

    Attributes:
        id: 모델 UUID.
        model_id: 공급사 API 모델 식별자.
        display_name: UI 표시 이름.
        provider: LLM 공급사.
        tier: 모델 등급.
        input_cost_per_1m: 입력 토큰 비용 (USD/1M).
        output_cost_per_1m: 출력 토큰 비용 (USD/1M).
        max_context_length: 최대 컨텍스트 토큰 수.
        agent_count: 이 모델을 사용하는 에이전트 수.
        total_wins: 해당 에이전트들의 누적 승리 합계.
        total_losses: 해당 에이전트들의 누적 패배 합계.
        total_draws: 해당 에이전트들의 누적 무승부 합계.
        win_rate: 승률 (0.0~1.0), 전적이 없으면 None.
    """

    id: UUID
    model_id: str
    display_name: str
    provider: str
    tier: str
    input_cost_per_1m: float
    output_cost_per_1m: float
    max_context_length: int
    agent_count: int
    total_wins: int
    total_losses: int
    total_draws: int
    win_rate: float | None
