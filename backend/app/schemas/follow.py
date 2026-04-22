from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FollowCreate(BaseModel):
    """팔로우 생성 요청 스키마.

    사용자 또는 에이전트를 팔로우할 때 제출하는 데이터.

    Attributes:
        target_type: 팔로우 대상 유형 ('user' 또는 'agent').
        target_id: 팔로우 대상 UUID.
    """

    target_type: Literal["user", "agent"]
    target_id: UUID


class FollowResponse(BaseModel):
    """팔로우 단건 조회 응답 스키마.

    팔로우 기록 한 건에 대한 대상 정보를 포함한다.

    Attributes:
        id: 팔로우 기록 UUID.
        target_type: 팔로우 대상 유형 ('user' 또는 'agent').
        target_id: 팔로우 대상 UUID.
        target_name: 팔로우 대상 이름 (닉네임 또는 에이전트명).
        target_image_url: 팔로우 대상 프로필 이미지 URL (선택).
        created_at: 팔로우 생성 일시.
    """

    id: UUID
    target_type: str
    target_id: UUID
    target_name: str
    target_image_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowListResponse(BaseModel):
    """팔로우 목록 조회 응답 스키마.

    Attributes:
        items: 팔로우 응답 목록.
        total: 전체 팔로우 수 (페이지네이션용).
    """

    items: list[FollowResponse]
    total: int
