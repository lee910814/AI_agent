from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ModelUsage(BaseModel):
    """모델별 토큰 사용량 집계 스키마.

    특정 LLM 모델에 대한 누적·일별·월별 사용 통계를 담는다.

    Attributes:
        model_name: LLM 모델 표시 이름.
        provider: LLM 공급자.
        tier: 모델 등급.
        credit_per_1k_tokens: 1,000 토큰당 크레딧 단가.
        input_cost_per_1m: 입력 토큰 비용 (USD/1M).
        output_cost_per_1m: 출력 토큰 비용 (USD/1M).
        input_tokens: 누적 입력 토큰 수.
        output_tokens: 누적 출력 토큰 수.
        cost: 누적 총 비용 (USD).
        request_count: 누적 요청 횟수.
        daily_input_tokens: 당일 입력 토큰 수.
        daily_output_tokens: 당일 출력 토큰 수.
        daily_cost: 당일 비용 (USD).
        daily_request_count: 당일 요청 횟수.
        monthly_input_tokens: 당월 입력 토큰 수.
        monthly_output_tokens: 당월 출력 토큰 수.
        monthly_cost: 당월 비용 (USD).
        monthly_request_count: 당월 요청 횟수.
    """

    model_name: str
    provider: str
    tier: str = "economy"
    credit_per_1k_tokens: int = 1
    input_cost_per_1m: float
    output_cost_per_1m: float
    input_tokens: int
    output_tokens: int
    cost: float
    request_count: int
    daily_input_tokens: int = 0
    daily_output_tokens: int = 0
    daily_cost: float = 0.0
    daily_request_count: int = 0
    monthly_input_tokens: int = 0
    monthly_output_tokens: int = 0
    monthly_cost: float = 0.0
    monthly_request_count: int = 0


class UsageSummary(BaseModel):
    """사용자 토큰 사용량 요약 스키마.

    사용자의 전체·일별·월별 LLM 사용량 집계와 모델별 분류를 포함한다.

    Attributes:
        total_input_tokens: 전체 누적 입력 토큰 수.
        total_output_tokens: 전체 누적 출력 토큰 수.
        total_cost: 전체 누적 비용 (USD).
        daily_input_tokens: 당일 입력 토큰 수.
        daily_output_tokens: 당일 출력 토큰 수.
        daily_cost: 당일 비용 (USD).
        monthly_input_tokens: 당월 입력 토큰 수.
        monthly_output_tokens: 당월 출력 토큰 수.
        monthly_cost: 당월 비용 (USD).
        by_model: 모델별 사용량 세부 목록.
    """

    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    daily_input_tokens: int
    daily_output_tokens: int
    daily_cost: float
    monthly_input_tokens: int
    monthly_output_tokens: int
    monthly_cost: float
    by_model: list[ModelUsage] = []


class UsageHistoryItem(BaseModel):
    """일별 사용량 이력 항목 스키마.

    하루 단위로 집계된 토큰 사용량과 비용을 나타낸다.

    Attributes:
        date: 날짜 문자열 (YYYY-MM-DD).
        input_tokens: 해당 날짜 입력 토큰 수.
        output_tokens: 해당 날짜 출력 토큰 수.
        cost: 해당 날짜 비용 (USD).
    """

    date: str
    input_tokens: int
    output_tokens: int
    cost: float


class ModelDailyUsage(BaseModel):
    """모델별 일별 사용량 스키마.

    특정 모델에 대한 하루 단위 사용량을 나타낸다.

    Attributes:
        date: 날짜 문자열 (YYYY-MM-DD).
        model_name: LLM 모델 이름.
        input_tokens: 해당 날짜 입력 토큰 수.
        output_tokens: 해당 날짜 출력 토큰 수.
        cost: 해당 날짜 비용 (USD).
    """

    date: str
    model_name: str
    input_tokens: int
    output_tokens: int
    cost: float


class UsageHistoryResponse(BaseModel):
    """사용량 이력 조회 응답 스키마.

    일별 집계와 모델별 일별 집계를 함께 반환한다.

    Attributes:
        daily: 날짜별 전체 사용량 목록.
        by_model_daily: 모델별 날짜별 사용량 목록.
    """

    daily: list[UsageHistoryItem]
    by_model_daily: list[ModelDailyUsage]


class TokenUsageLogResponse(BaseModel):
    """토큰 사용 로그 단건 응답 스키마.

    LLM 호출 한 건에 대한 상세 기록을 담는다.

    Attributes:
        id: 로그 레코드 ID.
        user_id: 호출을 발생시킨 사용자 UUID.
        session_id: 연관된 세션 UUID (선택).
        llm_model_id: 사용된 LLM 모델 UUID.
        input_tokens: 입력 토큰 수.
        output_tokens: 출력 토큰 수.
        cost: 해당 호출 비용 (USD).
        created_at: 로그 생성 일시.
    """

    id: int
    user_id: UUID
    session_id: UUID | None
    llm_model_id: UUID
    input_tokens: int
    output_tokens: int
    cost: float
    created_at: datetime

    model_config = {"from_attributes": True}
