from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# 템플릿 스키마
# ---------------------------------------------------------------------------

class AgentTemplateResponse(BaseModel):
    """사용자 공개 템플릿 응답 — base_system_prompt 미노출.

    일반 사용자에게 공개되는 에이전트 템플릿 정보.
    시스템 프롬프트 원본은 포함되지 않는다.

    Attributes:
        id: 템플릿 UUID.
        slug: URL-safe 식별자 (영문 소문자·숫자·밑줄).
        display_name: UI 표시 이름.
        description: 템플릿 설명 (선택).
        icon: 아이콘 식별자 (선택).
        customization_schema: 사용자 커스터마이징 가능 필드 스키마.
        default_values: 커스터마이징 기본값 딕셔너리.
        sort_order: 목록 정렬 순서.
        is_active: 현재 활성화 여부.
    """

    id: UUID
    slug: str
    display_name: str
    description: str | None
    icon: str | None
    customization_schema: dict
    default_values: dict
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class AgentTemplateAdminResponse(AgentTemplateResponse):
    """관리자 템플릿 응답 — base_system_prompt 포함.

    AgentTemplateResponse를 상속하며 관리자 전용 필드를 추가한다.

    Attributes:
        base_system_prompt: 템플릿 기반 시스템 프롬프트 원본.
        created_at: 템플릿 생성 일시.
        updated_at: 마지막 수정 일시.
    """

    base_system_prompt: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentTemplateCreate(BaseModel):
    """에이전트 템플릿 생성 요청 스키마.

    관리자가 새 에이전트 템플릿을 등록할 때 제출하는 데이터.

    Attributes:
        slug: URL-safe 식별자 (영문 소문자·숫자·밑줄, 1~50자).
        display_name: UI 표시 이름 (1~100자).
        description: 템플릿 설명 (선택).
        icon: 아이콘 식별자 (최대 50자, 선택).
        base_system_prompt: 기반 시스템 프롬프트 (1자 이상).
        customization_schema: 커스터마이징 가능 필드 스키마 딕셔너리.
        default_values: 커스터마이징 기본값 딕셔너리.
        sort_order: 정렬 순서 (기본 0).
        is_active: 활성화 여부 (기본 True).
    """

    slug: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    icon: str | None = Field(None, max_length=50)
    base_system_prompt: str = Field(..., min_length=1)
    customization_schema: dict
    default_values: dict
    sort_order: int = 0
    is_active: bool = True


class AgentTemplateUpdate(BaseModel):
    """에이전트 템플릿 수정 요청 스키마.

    관리자가 기존 템플릿을 부분 수정할 때 사용한다.
    전달된 필드만 업데이트된다.

    Attributes:
        display_name: 변경할 표시 이름 (1~100자, 선택).
        description: 변경할 설명 (선택).
        icon: 변경할 아이콘 식별자 (최대 50자, 선택).
        base_system_prompt: 변경할 기반 시스템 프롬프트 (1자 이상, 선택).
        customization_schema: 변경할 커스터마이징 스키마 (선택).
        default_values: 변경할 기본값 딕셔너리 (선택).
        sort_order: 변경할 정렬 순서 (선택).
        is_active: 변경할 활성화 여부 (선택).
    """

    display_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    icon: str | None = Field(None, max_length=50)
    base_system_prompt: str | None = Field(None, min_length=1)
    customization_schema: dict | None = None
    default_values: dict | None = None
    sort_order: int | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# 에이전트 스키마
# ---------------------------------------------------------------------------

class AgentCreate(BaseModel):
    """에이전트 생성 요청 스키마.

    사용자가 새 에이전트를 등록할 때 제출하는 데이터.
    직접 생성과 템플릿 기반 생성 두 가지 방식을 지원한다.

    Attributes:
        name: 에이전트 이름 (1~100자).
        description: 에이전트 설명 (선택).
        provider: LLM 공급자 ('openai', 'anthropic', 'google', 'runpod', 'local').
        model_id: 사용 모델 식별자 (기본 'custom').
        api_key: 사용자 제공 API 키 (선택, use_platform_credits=True이면 불필요).
        system_prompt: 에이전트 시스템 프롬프트 (선택).
        version_tag: 버전 태그 (선택).
        parameters: LLM 파라미터 딕셔너리 (선택).
        image_url: 프로필 이미지 URL (선택).
        is_system_prompt_public: 시스템 프롬프트 공개 여부.
        use_platform_credits: 플랫폼 크레딧으로 LLM 비용 지불 여부.
        template_id: 기반 템플릿 UUID (템플릿 기반 생성 시).
        customizations: 템플릿 커스터마이징 값 (선택).
        enable_free_text: 자유 텍스트 입력 허용 여부.
        is_profile_public: 프로필 공개 여부.
    """

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    provider: str = Field(..., pattern="^(openai|anthropic|google|runpod|local)$")
    model_id: str = Field("custom", min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1)
    system_prompt: str | None = Field(None, min_length=1)
    version_tag: str | None = None
    parameters: dict | None = None
    image_url: str | None = None
    is_system_prompt_public: bool = False
    use_platform_credits: bool = False
    # 템플릿 기반 생성 파라미터
    template_id: UUID | None = None
    customizations: dict | None = None
    enable_free_text: bool = False
    is_profile_public: bool = True


class AgentUpdate(BaseModel):
    """에이전트 수정 요청 스키마.

    사용자가 기존 에이전트 정보를 부분 수정할 때 사용한다.
    전달된 필드만 업데이트된다.

    Attributes:
        name: 변경할 이름 (1~100자, 선택).
        description: 변경할 설명 (선택).
        provider: 변경할 LLM 공급자 (선택).
        model_id: 변경할 모델 식별자 (선택).
        api_key: 변경할 API 키 (선택).
        system_prompt: 변경할 시스템 프롬프트 (선택).
        version_tag: 변경할 버전 태그 (선택).
        parameters: 변경할 LLM 파라미터 (선택).
        image_url: 변경할 프로필 이미지 URL (선택).
        is_system_prompt_public: 변경할 시스템 프롬프트 공개 여부 (선택).
        use_platform_credits: 변경할 플랫폼 크레딧 사용 여부 (선택).
        customizations: 변경할 템플릿 커스터마이징 값 (선택).
        enable_free_text: 변경할 자유 텍스트 허용 여부.
        is_profile_public: 변경할 프로필 공개 여부 (선택).
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    provider: str | None = Field(None, pattern="^(openai|anthropic|google|runpod|local)$")
    model_id: str | None = Field(None, min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1)
    system_prompt: str | None = Field(None, min_length=1)
    version_tag: str | None = None
    parameters: dict | None = None
    image_url: str | None = None
    is_system_prompt_public: bool | None = None
    use_platform_credits: bool | None = None
    # 템플릿 커스터마이징 변경
    customizations: dict | None = None
    enable_free_text: bool = False
    is_profile_public: bool | None = None


class AgentVersionResponse(BaseModel):
    """에이전트 버전 이력 조회 응답 스키마.

    에이전트의 특정 버전 스냅샷 정보를 담는다.

    Attributes:
        id: 버전 UUID.
        version_number: 버전 번호 (1부터 순차 증가).
        version_tag: 사용자 지정 버전 태그 (선택).
        system_prompt: 해당 버전의 시스템 프롬프트.
        parameters: 해당 버전의 LLM 파라미터 (선택).
        wins: 해당 버전의 승리 수.
        losses: 해당 버전의 패배 수.
        draws: 해당 버전의 무승부 수.
        created_at: 버전 생성 일시.
    """

    id: UUID
    version_number: int
    version_tag: str | None
    system_prompt: str
    parameters: dict | None
    wins: int
    losses: int
    draws: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentResponse(BaseModel):
    """에이전트 소유자 응답 스키마.

    에이전트 소유자에게 반환되는 전체 정보 (API 키 제외).

    Attributes:
        id: 에이전트 UUID.
        owner_id: 소유자 사용자 UUID.
        name: 에이전트 이름.
        description: 에이전트 설명 (선택).
        provider: LLM 공급자.
        model_id: 사용 모델 식별자.
        image_url: 프로필 이미지 URL (선택).
        elo_rating: 현재 ELO 점수.
        wins: 총 승리 수.
        losses: 총 패배 수.
        draws: 총 무승부 수.
        win_rate: 승률 (소수점 1자리, 0~100).
        is_active: 활성화 여부.
        is_platform: 플랫폼 공식 에이전트 여부.
        is_connected: 현재 WebSocket 연결 여부.
        is_system_prompt_public: 시스템 프롬프트 공개 여부.
        use_platform_credits: 플랫폼 크레딧 사용 여부.
        name_changed_at: 마지막 이름 변경 일시 (선택).
        template_id: 기반 템플릿 UUID (선택).
        customizations: 템플릿 커스터마이징 값 (선택).
        tier: 현재 티어 (예: 'Iron', 'Bronze', 'Silver').
        tier_protection_count: 티어 강등 보호 횟수 잔여.
        active_series_id: 진행 중인 승급전/강등전 시리즈 UUID (선택).
        is_profile_public: 프로필 공개 여부.
        follower_count: 팔로워 수.
        is_following: 현재 사용자의 팔로우 여부.
        created_at: 에이전트 생성 일시.
        updated_at: 마지막 수정 일시.
    """

    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    provider: str
    model_id: str
    image_url: str | None = None
    elo_rating: int
    wins: int
    losses: int
    draws: int
    win_rate: float = 0.0  # wins / total * 100 (소수점 1자리)
    is_active: bool
    is_platform: bool = False
    is_connected: bool = False
    is_system_prompt_public: bool = False
    use_platform_credits: bool = False
    name_changed_at: datetime | None = None
    template_id: UUID | None
    customizations: dict | None
    tier: str = "Iron"
    tier_protection_count: int = 0
    active_series_id: UUID | None = None
    is_profile_public: bool = True
    follower_count: int = 0
    is_following: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_win_rate(self) -> "AgentResponse":
        """승률을 계산해 win_rate 필드를 채운다.

        Returns:
            win_rate가 설정된 AgentResponse 인스턴스.
        """
        total = self.wins + self.losses + self.draws
        self.win_rate = round(self.wins / total * 100, 1) if total > 0 else 0.0
        return self


class AgentPublicResponse(BaseModel):
    """비소유자 공개 응답 — customizations 미노출. is_system_prompt_public=True이면 system_prompt 포함.

    에이전트 소유자가 아닌 사용자에게 반환되는 공개 정보.
    커스터마이징 상세는 노출되지 않으며, 시스템 프롬프트는 공개 설정된 경우에만 포함된다.

    Attributes:
        id: 에이전트 UUID.
        owner_id: 소유자 사용자 UUID.
        name: 에이전트 이름.
        description: 에이전트 설명 (선택).
        provider: LLM 공급자.
        model_id: 사용 모델 식별자.
        image_url: 프로필 이미지 URL (선택).
        elo_rating: 현재 ELO 점수.
        wins: 총 승리 수.
        losses: 총 패배 수.
        draws: 총 무승부 수.
        win_rate: 승률 (소수점 1자리).
        is_active: 활성화 여부.
        is_platform: 플랫폼 공식 에이전트 여부.
        is_connected: 현재 WebSocket 연결 여부.
        is_system_prompt_public: 시스템 프롬프트 공개 여부.
        system_prompt: 시스템 프롬프트 (is_system_prompt_public=True일 때만 채워짐).
        tier: 현재 티어.
        is_profile_public: 프로필 공개 여부.
        follower_count: 팔로워 수.
        is_following: 현재 사용자의 팔로우 여부.
        created_at: 에이전트 생성 일시.
        updated_at: 마지막 수정 일시.
    """

    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    provider: str
    model_id: str
    image_url: str | None = None
    elo_rating: int
    wins: int
    losses: int
    draws: int
    win_rate: float = 0.0
    is_active: bool
    is_platform: bool = False
    is_connected: bool = False
    is_system_prompt_public: bool = False
    system_prompt: str | None = None  # is_system_prompt_public=True일 때만 채워짐
    tier: str = "Iron"
    is_profile_public: bool = True
    follower_count: int = 0
    is_following: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_win_rate(self) -> "AgentPublicResponse":
        """승률을 계산해 win_rate 필드를 채운다.

        Returns:
            win_rate가 설정된 AgentPublicResponse 인스턴스.
        """
        total = self.wins + self.losses + self.draws
        self.win_rate = round(self.wins / total * 100, 1) if total > 0 else 0.0
        return self


class AgentRankingResponse(BaseModel):
    """에이전트 랭킹 목록 항목 스키마.

    랭킹 조회 시 반환되는 경량화된 에이전트 정보.

    Attributes:
        id: 에이전트 UUID.
        name: 에이전트 이름.
        owner_nickname: 소유자 닉네임.
        owner_id: 소유자 사용자 UUID.
        provider: LLM 공급자.
        model_id: 사용 모델 식별자.
        elo_rating: 현재 ELO 점수.
        wins: 총 승리 수.
        losses: 총 패배 수.
        draws: 총 무승부 수.
        image_url: 프로필 이미지 URL (선택).
        tier: 현재 티어.
        is_profile_public: 프로필 공개 여부.
    """

    id: UUID
    name: str
    owner_nickname: str
    owner_id: UUID
    provider: str
    model_id: str
    elo_rating: int
    wins: int
    losses: int
    draws: int
    image_url: str | None = None
    tier: str = "Iron"
    is_profile_public: bool = True

    model_config = {"from_attributes": True}


class HeadToHeadEntry(BaseModel):
    """상대 에이전트별 H2H(맞대결) 통계 항목 스키마.

    특정 상대와의 전체 대결 기록 및 승률을 담는다.

    Attributes:
        opponent_id: 상대 에이전트 ID 문자열.
        opponent_name: 상대 에이전트 이름.
        opponent_image_url: 상대 프로필 이미지 URL (선택).
        total_matches: 총 대결 수.
        wins: 승리 수.
        losses: 패배 수.
        draws: 무승부 수.
        win_rate: 승률 (소수점 1자리).
    """

    opponent_id: str
    opponent_name: str
    opponent_image_url: str | None = None
    total_matches: int
    wins: int
    losses: int
    draws: int
    win_rate: float = 0.0

    @model_validator(mode="after")
    def compute_win_rate(self) -> "HeadToHeadEntry":
        """승률을 계산해 win_rate 필드를 채운다.

        Returns:
            win_rate가 설정된 HeadToHeadEntry 인스턴스.
        """
        total = self.wins + self.losses + self.draws
        self.win_rate = round(self.wins / total * 100, 1) if total > 0 else 0.0
        return self


class GalleryEntry(BaseModel):
    """갤러리 에이전트 항목 스키마.

    공개 갤러리에 표시되는 에이전트 카드 정보.

    Attributes:
        id: 에이전트 UUID.
        name: 에이전트 이름.
        description: 에이전트 설명 (선택).
        provider: LLM 공급자.
        model_id: 사용 모델 식별자.
        image_url: 프로필 이미지 URL (선택).
        elo_rating: 현재 ELO 점수.
        wins: 총 승리 수.
        losses: 총 패배 수.
        draws: 총 무승부 수.
        tier: 현재 티어.
        owner_nickname: 소유자 닉네임.
        is_system_prompt_public: 시스템 프롬프트 공개 여부.
        created_at: 에이전트 생성 일시.
    """

    id: UUID
    name: str
    description: str | None = None
    provider: str
    model_id: str
    image_url: str | None = None
    elo_rating: int
    wins: int
    losses: int
    draws: int
    tier: str
    owner_nickname: str
    is_system_prompt_public: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}


class CloneRequest(BaseModel):
    """에이전트 클론 요청 스키마.

    갤러리의 공개 에이전트를 복제해 자신의 에이전트로 만들 때 사용한다.

    Attributes:
        name: 복제할 에이전트에 부여할 새 이름 (1~100자).
    """

    name: str = Field(..., min_length=1, max_length=100)


class PromotionSeriesResponse(BaseModel):
    """승급전/강등전 시리즈 응답 스키마.

    에이전트의 현재 또는 완료된 승급전·강등전 시리즈 상세 정보.

    Attributes:
        id: 시리즈 UUID.
        agent_id: 대상 에이전트 UUID.
        series_type: 시리즈 유형 ('promotion' 또는 'demotion').
        from_tier: 현재 티어.
        to_tier: 목표 티어.
        required_wins: 승급/강등 유지에 필요한 승리 수.
        current_wins: 현재까지 획득한 승리 수.
        current_losses: 현재까지의 패배 수.
        status: 시리즈 상태 ('in_progress', 'success', 'failed').
        created_at: 시리즈 시작 일시.
        completed_at: 시리즈 완료 일시 (진행 중이면 None).
    """

    id: UUID
    agent_id: UUID
    series_type: str
    from_tier: str
    to_tier: str
    required_wins: int
    current_wins: int
    current_losses: int
    status: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 페이지네이션 래퍼
# ---------------------------------------------------------------------------

class AgentRankingListResponse(BaseModel):
    """에이전트 랭킹 목록 응답 스키마.

    Attributes:
        items: 랭킹 항목 목록.
        total: 전체 에이전트 수 (페이지네이션용).
    """

    items: list[AgentRankingResponse]
    total: int


class GalleryListResponse(BaseModel):
    """갤러리 에이전트 목록 응답 스키마.

    Attributes:
        items: 갤러리 항목 목록.
        total: 전체 공개 에이전트 수 (페이지네이션용).
    """

    items: list[GalleryEntry]
    total: int


class HeadToHeadListResponse(BaseModel):
    """H2H 통계 목록 응답 스키마.

    Attributes:
        items: 상대별 맞대결 통계 목록.
    """

    items: list[HeadToHeadEntry]
