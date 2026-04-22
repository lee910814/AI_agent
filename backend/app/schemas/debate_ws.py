"""WebSocket 프로토콜 메시지 스키마. 로컬 에이전트와 서버 간 통신 형식 정의."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class WSTurnRequest(BaseModel):
    """서버 → 에이전트: 턴 요청.

    서버가 에이전트에게 이번 턴의 발언을 요청할 때 전송하는 메시지.

    Attributes:
        type: 메시지 타입 식별자 (항상 'turn_request').
        match_id: 현재 매치 UUID.
        turn_number: 현재 턴 번호.
        speaker: 발언 측 식별자 ('A' 또는 'B').
        topic_title: 토론 주제 제목.
        topic_description: 토론 주제 상세 설명 (선택).
        max_turns: 매치 총 최대 턴 수.
        turn_token_limit: 이번 발언 최대 토큰 수.
        my_previous_claims: 내 이전 주장 목록.
        opponent_previous_claims: 상대방 이전 주장 목록.
        time_limit_seconds: 응답 제한 시간(초).
        available_tools: 이번 턴에 사용 가능한 툴 목록.
    """

    type: Literal["turn_request"] = "turn_request"
    match_id: UUID
    turn_number: int
    speaker: str
    topic_title: str
    topic_description: str | None
    max_turns: int
    turn_token_limit: int
    my_previous_claims: list[str]
    opponent_previous_claims: list[str]
    time_limit_seconds: int
    available_tools: list[str] = []  # 서버가 지원하는 툴 목록


class WSTurnResponse(BaseModel):
    """에이전트 → 서버: 턴 최종 응답.

    에이전트가 발언을 완료한 후 서버에 전송하는 메시지.

    Attributes:
        type: 메시지 타입 식별자 (항상 'turn_response').
        match_id: 현재 매치 UUID.
        action: 에이전트가 취한 행동 유형 (예: 'claim', 'concede').
        claim: 에이전트의 주장 텍스트.
        evidence: 주장을 뒷받침하는 근거 (선택).
        tool_used: 이번 턴에 사용한 툴 이름 (선택).
        tool_result: 툴 실행 결과 텍스트 (선택).
    """

    type: Literal["turn_response"] = "turn_response"
    match_id: UUID
    action: str
    claim: str
    evidence: str | None = None
    tool_used: str | None = None
    tool_result: str | None = None


class WSToolRequest(BaseModel):
    """에이전트 → 서버: 툴 실행 요청.

    에이전트가 최종 응답(turn_response)을 보내기 전에
    서버 측 툴을 호출할 때 사용한다.

    Attributes:
        type: 메시지 타입 식별자 (항상 'tool_request').
        match_id: 현재 매치 UUID.
        turn_number: 현재 턴 번호.
        tool_name: 실행할 툴 이름 ('calculator', 'stance_tracker', 'opponent_summary', 'turn_info').
        tool_input: 툴에 전달할 입력값 (calculator는 수식, 나머지는 빈 문자열).
    """

    type: Literal["tool_request"] = "tool_request"
    match_id: UUID
    turn_number: int
    tool_name: str  # "calculator" | "stance_tracker" | "opponent_summary" | "turn_info"
    tool_input: str = ""  # calculator용 수식, 나머지 툴은 빈 문자열


class WSToolResult(BaseModel):
    """서버 → 에이전트: 툴 실행 결과.

    서버가 툴 요청을 처리한 후 에이전트에게 반환하는 메시지.

    Attributes:
        type: 메시지 타입 식별자 (항상 'tool_result').
        tool_name: 실행된 툴 이름.
        result: 툴 실행 결과 텍스트.
        error: 실행 중 오류 메시지 (선택, 오류 없으면 None).
    """

    type: Literal["tool_result"] = "tool_result"
    tool_name: str
    result: str
    error: str | None = None


class WSMatchReady(BaseModel):
    """서버 → 에이전트: 매치 시작 알림.

    매치가 시작될 준비가 됐을 때 서버가 에이전트에게 보내는 메시지.

    Attributes:
        type: 메시지 타입 식별자 (항상 'match_ready').
        match_id: 시작할 매치 UUID.
        topic_title: 토론 주제 제목.
        opponent_name: 상대 에이전트 이름.
        your_side: 자신이 맡은 토론 측 ('A' 또는 'B').
    """

    type: Literal["match_ready"] = "match_ready"
    match_id: UUID
    topic_title: str
    opponent_name: str
    your_side: str


class WSError(BaseModel):
    """서버 → 에이전트: 에러.

    서버에서 처리 중 오류가 발생했을 때 에이전트에게 전송하는 메시지.

    Attributes:
        type: 메시지 타입 식별자 (항상 'error').
        message: 오류 설명 메시지.
        code: 오류 코드 문자열 (선택).
    """

    type: Literal["error"] = "error"
    message: str
    code: str | None = None


class WSHeartbeat(BaseModel):
    """WebSocket 연결 유지용 핑/퐁 메시지.

    Attributes:
        type: 'ping' (클라이언트 → 서버) 또는 'pong' (서버 → 클라이언트).
    """

    type: Literal["ping", "pong"]
