from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SeasonCreate(BaseModel):
    """시즌 생성 요청 스키마.

    관리자가 새 토론 시즌을 개설할 때 제출하는 데이터.

    Attributes:
        season_number: 시즌 번호 (1부터 순차 증가).
        title: 시즌 표시 제목.
        start_at: 시즌 시작 일시.
        end_at: 시즌 종료 일시.
    """

    season_number: int
    title: str
    start_at: datetime
    end_at: datetime


class SeasonResponse(BaseModel):
    """시즌 조회 응답 스키마.

    클라이언트에 반환되는 시즌 상세 정보.

    Attributes:
        id: 시즌 UUID.
        season_number: 시즌 번호.
        title: 시즌 제목.
        start_at: 시즌 시작 일시.
        end_at: 시즌 종료 일시.
        status: 시즌 상태 ('upcoming', 'active', 'closed').
        created_at: 시즌 생성 일시.
    """

    id: UUID
    season_number: int
    title: str
    start_at: datetime
    end_at: datetime
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SeasonResultResponse(BaseModel):
    """시즌 종료 결과 항목 스키마.

    시즌이 종료된 후 최종 순위와 보상 정보를 담는 단건 결과.

    Attributes:
        rank: 최종 순위.
        agent_id: 에이전트 UUID.
        agent_name: 에이전트 이름.
        agent_image_url: 에이전트 프로필 이미지 URL (선택).
        final_elo: 시즌 종료 시 최종 ELO 점수.
        final_tier: 시즌 종료 시 최종 티어.
        wins: 시즌 내 승리 수.
        losses: 시즌 내 패배 수.
        draws: 시즌 내 무승부 수.
        reward_credits: 순위에 따라 지급된 크레딧.
    """

    rank: int
    agent_id: UUID
    agent_name: str
    agent_image_url: str | None = None
    final_elo: int
    final_tier: str
    wins: int
    losses: int
    draws: int
    reward_credits: int
