from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class JoinQueueRequest(BaseModel):
    """매칭 큐 참가 요청 스키마.

    에이전트를 매칭 대기 큐에 등록할 때 사용한다.

    Attributes:
        agent_id: 큐에 등록할 에이전트 UUID.
        password: 비공개 토픽 참가 시 필요한 비밀번호 (선택).
    """

    agent_id: UUID = Field(...)
    password: str | None = None


class AgentSummary(BaseModel):
    """매치 내 에이전트 요약 정보 스키마.

    매치 응답에 포함되는 경량화된 에이전트 정보.

    Attributes:
        id: 에이전트 UUID.
        name: 에이전트 이름.
        provider: LLM 공급자.
        model_id: 사용 모델 식별자.
        elo_rating: 현재 ELO 점수.
        image_url: 프로필 이미지 URL (선택).
    """

    id: UUID
    name: str
    provider: str
    model_id: str
    elo_rating: int
    image_url: str | None = None

    model_config = {"from_attributes": True}


class TurnLogResponse(BaseModel):
    """턴 로그 조회 응답 스키마.

    매치의 개별 턴 발언 기록과 검토 결과를 담는다.

    Attributes:
        id: 턴 로그 UUID.
        turn_number: 턴 번호.
        speaker: 발언 측 식별자 ('A' 또는 'B').
        agent_id: 발언한 에이전트 UUID.
        action: 행동 유형 (예: 'claim', 'concede').
        claim: 발언 내용.
        evidence: 주장 근거 (선택).
        tool_used: 사용한 툴 이름 (선택).
        tool_result: 툴 실행 결과 (선택).
        penalties: 위반 항목별 벌점 딕셔너리 (선택).
        penalty_total: 총 벌점 합계.
        human_suspicion_score: 사람 발언 유사도 의심 점수.
        response_time_ms: 발언 생성 소요 시간(ms) (선택).
        input_tokens: 입력 토큰 수.
        output_tokens: 출력 토큰 수.
        review_result: LLM 검토 결과 딕셔너리 (선택).
        is_blocked: 검토로 인해 발언이 차단됐는지 여부.
        created_at: 턴 생성 일시.
    """

    id: UUID
    turn_number: int
    speaker: str
    agent_id: UUID
    action: str
    claim: str
    evidence: str | None
    tool_used: str | None
    tool_result: str | None
    penalties: dict | None
    penalty_total: int
    human_suspicion_score: int = 0
    response_time_ms: int | None = None
    input_tokens: int
    output_tokens: int
    review_result: dict | None = None
    is_blocked: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ScorecardResponse(BaseModel):
    """매치 스코어카드 응답 스키마.

    최종 판정 결과 및 에이전트별 점수를 담는다.

    Attributes:
        agent_a: A 측 에이전트 점수 딕셔너리.
        agent_b: B 측 에이전트 점수 딕셔너리.
        reasoning: 판정 근거 설명.
        winner_id: 승자 에이전트 UUID (무승부이면 None).
        result: 결과 문자열 ('a_win', 'b_win', 'draw').
    """

    agent_a: dict
    agent_b: dict
    reasoning: str
    winner_id: UUID | None
    result: str


class MatchResponse(BaseModel):
    """매치 상세 조회 응답 스키마.

    클라이언트에 반환되는 매치 전체 정보.

    Attributes:
        id: 매치 UUID.
        topic_id: 토론 주제 UUID.
        topic_title: 토론 주제 제목.
        agent_a: A 측 에이전트 요약.
        agent_b: B 측 에이전트 요약.
        status: 매치 상태 ('pending', 'in_progress', 'completed', 'error', 'waiting_agent', 'forfeit').
        winner_id: 승자 에이전트 UUID (선택).
        score_a: A 측 점수.
        score_b: B 측 점수.
        penalty_a: A 측 누적 벌점.
        penalty_b: B 측 누적 벌점.
        turn_count: 진행된 총 턴 수.
        started_at: 매치 시작 일시 (선택).
        finished_at: 매치 종료 일시 (선택).
        elo_a_before: A 측 매치 전 ELO (선택).
        elo_b_before: B 측 매치 전 ELO (선택).
        elo_a_after: A 측 매치 후 ELO (선택).
        elo_b_after: B 측 매치 후 ELO (선택).
        match_type: 매치 유형 ('ranked', 'promotion', 'demotion').
        series_id: 연관 승급전 시리즈 UUID (선택).
        created_at: 매치 생성 일시.
    """

    id: UUID
    topic_id: UUID
    topic_title: str
    agent_a: AgentSummary
    agent_b: AgentSummary
    status: str
    winner_id: UUID | None
    score_a: int
    score_b: int
    penalty_a: int
    penalty_b: int
    turn_count: int = 0
    started_at: datetime | None
    finished_at: datetime | None
    elo_a_before: int | None = None
    elo_b_before: int | None = None
    elo_a_after: int | None = None
    elo_b_after: int | None = None
    match_type: str = "ranked"
    series_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchListResponse(BaseModel):
    """매치 목록 조회 응답 스키마.

    Attributes:
        items: 매치 응답 목록.
        total: 전체 매치 수 (페이지네이션용).
    """

    items: list[MatchResponse]
    total: int


class MatchStreamEvent(BaseModel):
    """SSE로 전송되는 이벤트.

    실시간 매치 스트리밍에서 클라이언트로 전송되는 개별 이벤트.

    Attributes:
        event: 이벤트 타입 ('turn', 'penalty', 'finished', 'error').
        data: 이벤트 데이터 딕셔너리.
    """

    event: str  # turn, penalty, finished, error
    data: dict


class PredictionCreate(BaseModel):
    """예측투표 생성 요청 스키마.

    매치 시작 전 사용자가 승자를 예측할 때 사용한다.

    Attributes:
        prediction: 예측 값 ('a_win', 'b_win', 'draw' 중 하나).
    """

    prediction: str = Field(..., pattern="^(a_win|b_win|draw)$")


class PredictionStats(BaseModel):
    """예측투표 통계 응답 스키마.

    매치에 대한 전체 예측투표 현황과 내 투표 결과를 담는다.

    Attributes:
        a_win: A 측 승리 예측 수.
        b_win: B 측 승리 예측 수.
        draw: 무승부 예측 수.
        total: 전체 투표 수.
        my_prediction: 현재 사용자의 예측 값 (미투표이면 None).
        is_correct: 내 예측의 정답 여부 (매치 진행 중이면 None).
    """

    a_win: int = 0
    b_win: int = 0
    draw: int = 0
    total: int = 0
    my_prediction: str | None = None
    is_correct: bool | None = None
