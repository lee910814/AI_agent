from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TournamentCreate(BaseModel):
    """토너먼트 생성 요청 스키마.

    관리자가 새 토너먼트를 개설할 때 제출하는 데이터.

    Attributes:
        title: 토너먼트 제목 (1~200자).
        topic_id: 토너먼트에서 사용할 토론 주제 UUID.
        bracket_size: 토너먼트 대진표 규모 (4, 8, 16 중 하나).
    """

    title: str = Field(..., min_length=1, max_length=200)
    topic_id: UUID
    bracket_size: int = Field(..., ge=4, le=16)


class TournamentEntryResponse(BaseModel):
    """토너먼트 참가자 응답 스키마.

    대진표에 등록된 개별 에이전트 정보를 나타낸다.

    Attributes:
        id: 참가 기록 UUID.
        agent_id: 참가 에이전트 UUID.
        agent_name: 에이전트 이름.
        agent_image_url: 에이전트 프로필 이미지 URL (선택).
        seed: 시드 번호 (대진표 배정 순서).
        eliminated_at: 탈락 일시 (아직 진행 중이면 None).
        eliminated_round: 탈락한 라운드 번호 (선택).
    """

    id: UUID
    agent_id: UUID
    agent_name: str
    agent_image_url: str | None = None
    seed: int
    eliminated_at: datetime | None = None
    eliminated_round: int | None = None


class TournamentResponse(BaseModel):
    """토너먼트 조회 응답 스키마.

    클라이언트에 반환되는 토너먼트 상세 정보와 참가자 목록.

    Attributes:
        id: 토너먼트 UUID.
        title: 토너먼트 제목.
        topic_id: 토론 주제 UUID.
        status: 진행 상태 ('pending', 'in_progress', 'finished').
        bracket_size: 대진표 규모.
        current_round: 현재 진행 중인 라운드 번호.
        winner_agent_id: 우승 에이전트 UUID (진행 중이면 None).
        started_at: 토너먼트 시작 일시 (선택).
        finished_at: 토너먼트 종료 일시 (선택).
        created_at: 토너먼트 생성 일시.
        entries: 참가자 목록.
    """

    id: UUID
    title: str
    topic_id: UUID
    status: str
    bracket_size: int
    current_round: int
    winner_agent_id: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    entries: list[TournamentEntryResponse] = []
