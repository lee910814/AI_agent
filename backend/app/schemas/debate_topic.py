from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TopicCreate(BaseModel):
    """토론 주제 생성 요청 스키마.

    사용자 또는 관리자가 새 토론 주제를 등록할 때 제출하는 데이터.
    예약 시간을 지정하는 경우 종료 시각이 시작 시각보다 뒤여야 한다.

    Attributes:
        title: 토론 주제 제목 (1~200자).
        description: 주제 상세 설명 (선택).
        mode: 토론 형식 ('debate', 'persuasion', 'cross_exam').
        max_turns: 최대 턴 수 (2~20, 기본 6).
        turn_token_limit: 턴당 최대 토큰 수 (100~4000, 기본 1500).
        scheduled_start_at: 예약 시작 일시 (선택).
        scheduled_end_at: 예약 종료 일시 (선택).
        tools_enabled: 에이전트 툴 사용 허용 여부.
        password: 비공개 주제 접근 비밀번호 (선택).
    """

    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    mode: str = Field("debate", pattern="^(debate|persuasion|cross_exam)$")
    max_turns: int = Field(6, ge=2, le=20)
    turn_token_limit: int = Field(1500, ge=100, le=4000)
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    tools_enabled: bool = True
    password: str | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "TopicCreate":
        """예약 시간 유효성을 검증한다.

        Returns:
            검증된 TopicCreate 인스턴스.

        Raises:
            ValueError: 종료 시각이 시작 시각보다 앞서거나 같은 경우.
        """
        if self.scheduled_end_at and self.scheduled_start_at and self.scheduled_end_at <= self.scheduled_start_at:
            raise ValueError("종료 시각은 시작 시각보다 뒤여야 합니다.")
        return self


class TopicUpdate(BaseModel):
    """토론 주제 수정 요청 스키마.

    관리자가 기존 토론 주제를 부분 수정할 때 사용한다.
    전달된 필드만 업데이트된다.

    Attributes:
        title: 변경할 제목 (1~200자, 선택).
        description: 변경할 설명 (선택).
        status: 변경할 상태 ('scheduled', 'open', 'in_progress', 'closed', 선택).
        max_turns: 변경할 최대 턴 수 (2~20, 선택).
        turn_token_limit: 변경할 턴당 토큰 제한 (100~4000, 선택).
        scheduled_start_at: 변경할 예약 시작 일시 (선택).
        scheduled_end_at: 변경할 예약 종료 일시 (선택).
        tools_enabled: 변경할 툴 허용 여부 (선택).
    """

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = Field(None, pattern="^(scheduled|open|in_progress|closed)$")
    max_turns: int | None = Field(None, ge=2, le=20)
    turn_token_limit: int | None = Field(None, ge=100, le=4000)
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    tools_enabled: bool | None = None


class TopicResponse(BaseModel):
    """토론 주제 조회 응답 스키마.

    클라이언트에 반환되는 토론 주제 상세 정보.

    Attributes:
        id: 주제 UUID.
        title: 주제 제목.
        description: 주제 설명 (선택).
        mode: 토론 형식.
        status: 현재 상태.
        max_turns: 최대 턴 수.
        turn_token_limit: 턴당 토큰 제한.
        scheduled_start_at: 예약 시작 일시 (선택).
        scheduled_end_at: 예약 종료 일시 (선택).
        is_admin_topic: 관리자가 생성한 주제 여부.
        tools_enabled: 툴 사용 허용 여부.
        queue_count: 현재 큐 대기 에이전트 수.
        match_count: 이 주제로 진행된 총 매치 수.
        is_password_protected: 비밀번호 보호 여부.
        created_at: 생성 일시.
        updated_at: 마지막 수정 일시.
        created_by: 생성자 UUID (선택).
        creator_nickname: 생성자 닉네임 (선택).
    """

    id: UUID
    title: str
    description: str | None
    mode: str
    status: str
    max_turns: int
    turn_token_limit: int
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    is_admin_topic: bool
    tools_enabled: bool
    queue_count: int = 0
    match_count: int = 0
    is_password_protected: bool = False
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
    creator_nickname: str | None = None

    model_config = {"from_attributes": True}


class TopicListResponse(BaseModel):
    """토론 주제 목록 조회 응답 스키마.

    Attributes:
        items: 주제 응답 목록.
        total: 전체 주제 수 (페이지네이션용).
    """

    items: list[TopicResponse]
    total: int


class TopicUpdatePayload(BaseModel):
    """토론 주제 관리자 수정 요청 스키마.

    관리 API에서 주제의 제목·설명·설정을 부분 수정할 때 사용한다.
    TopicUpdate와 달리 status 필드가 없으며, mode 변경을 허용한다.

    Attributes:
        title: 변경할 제목 (선택).
        description: 변경할 설명 (선택).
        mode: 변경할 토론 형식 (선택).
        max_turns: 변경할 최대 턴 수 (2~20, 선택).
        turn_token_limit: 변경할 턴당 토큰 제한 (100~4000, 선택).
        tools_enabled: 변경할 툴 허용 여부 (선택).
        scheduled_start_at: 변경할 예약 시작 일시 (선택).
        scheduled_end_at: 변경할 예약 종료 일시 (선택).
    """

    title: str | None = None
    description: str | None = None
    mode: str | None = Field(None, pattern="^(debate|persuasion|cross_exam)$")
    max_turns: int | None = Field(None, ge=2, le=20)
    turn_token_limit: int | None = Field(None, ge=100, le=4000)
    tools_enabled: bool | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
