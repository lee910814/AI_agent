from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    """알림 단건 조회 응답 스키마.

    사용자에게 발송된 개별 알림 정보를 담는다.

    Attributes:
        id: 알림 UUID.
        type: 알림 유형 (예: 'match_result', 'series_update', 'season_reward').
        title: 알림 제목.
        body: 알림 본문 (선택).
        link: 알림 클릭 시 이동할 URL (선택).
        is_read: 읽음 여부.
        created_at: 알림 생성 일시.
    """

    id: UUID
    type: str
    title: str
    body: str | None
    link: str | None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """알림 목록 조회 응답 스키마.

    Attributes:
        items: 알림 응답 목록.
        total: 전체 알림 수 (페이지네이션용).
        unread_count: 읽지 않은 알림 수.
    """

    items: list[NotificationResponse]
    total: int
    unread_count: int
