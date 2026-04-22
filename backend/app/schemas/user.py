import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    """사용자 회원가입 요청 스키마.

    신규 계정 생성 시 클라이언트가 제출하는 데이터.
    로그인 ID·닉네임·비밀번호에 대한 형식 검증을 포함한다.

    Attributes:
        login_id: 로그인에 사용할 영문/숫자/밑줄 조합 아이디 (2~30자).
        nickname: 서비스 내 표시 닉네임 (한글·영문·숫자·밑줄, 2~20자).
        password: 비밀번호 (영문+숫자 포함, 8~100자).
        email: 이메일 주소 (선택).
    """

    login_id: str
    nickname: str
    password: str
    email: str | None = None

    @field_validator("login_id")
    @classmethod
    def validate_login_id(cls, v: str) -> str:
        """로그인 ID 형식을 검증한다.

        Args:
            v: 검증할 로그인 ID 문자열.

        Returns:
            공백이 제거된 검증된 로그인 ID.

        Raises:
            ValueError: 길이가 2~30자 범위를 벗어나거나 허용되지 않는 문자가 포함된 경우.
        """
        v = v.strip()
        if len(v) < 2:
            raise ValueError("아이디는 2자 이상이어야 합니다")
        if len(v) > 30:
            raise ValueError("아이디는 30자 이하여야 합니다")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("아이디는 영문, 숫자, 밑줄(_)만 사용 가능합니다")
        return v

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        """닉네임 형식을 검증한다.

        Args:
            v: 검증할 닉네임 문자열.

        Returns:
            공백이 제거된 검증된 닉네임.

        Raises:
            ValueError: 길이가 2~20자 범위를 벗어나거나 허용되지 않는 문자가 포함된 경우.
        """
        v = v.strip()
        if len(v) < 2:
            raise ValueError("닉네임은 2자 이상이어야 합니다")
        if len(v) > 20:
            raise ValueError("닉네임은 20자 이하여야 합니다")
        if not re.match(r"^[a-zA-Z0-9가-힣_]+$", v):
            raise ValueError("닉네임은 한글, 영문, 숫자, 밑줄(_)만 사용 가능합니다")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """비밀번호 복잡도를 검증한다.

        Args:
            v: 검증할 비밀번호 문자열.

        Returns:
            검증된 비밀번호 문자열.

        Raises:
            ValueError: 길이가 8~100자 범위를 벗어나거나 영문자·숫자가 포함되지 않은 경우.
        """
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다")
        if len(v) > 100:
            raise ValueError("비밀번호는 100자 이하여야 합니다")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("비밀번호에 영문자가 포함되어야 합니다")
        if not re.search(r"\d", v):
            raise ValueError("비밀번호에 숫자가 포함되어야 합니다")
        return v


class UserLogin(BaseModel):
    """사용자 로그인 요청 스키마.

    Attributes:
        login_id: 로그인 아이디.
        password: 비밀번호.
    """

    login_id: str
    password: str


class UserResponse(BaseModel):
    """사용자 기본 정보 응답 스키마.

    로그인된 사용자 자신의 계정 정보를 반환할 때 사용한다.

    Attributes:
        id: 사용자 UUID.
        login_id: 로그인 아이디.
        nickname: 표시 닉네임.
        role: 역할 ('user', 'admin', 'superadmin').
        age_group: 연령 그룹 ('minor_safe', 'adult').
        adult_verified_at: 성인 인증 완료 일시 (미인증이면 None).
        preferred_llm_model_id: 선호 LLM 모델 UUID (선택).
        preferred_themes: 선호 테마 목록 (선택).
        created_at: 계정 생성 일시.
    """

    id: UUID
    login_id: str
    nickname: str
    role: str
    age_group: str
    adult_verified_at: datetime | None = None
    preferred_llm_model_id: UUID | None = None
    preferred_themes: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """사용자 정보 수정 요청 스키마.

    사용자가 자신의 닉네임 또는 선호 테마를 변경할 때 사용한다.

    Attributes:
        nickname: 변경할 닉네임 (선택).
        preferred_themes: 변경할 선호 테마 목록 (선택).
    """

    nickname: str | None = None
    preferred_themes: list[str] | None = None


class PasswordChange(BaseModel):
    """비밀번호 변경 요청 스키마.

    현재 비밀번호 확인 후 새 비밀번호로 교체할 때 사용한다.

    Attributes:
        current_password: 현재 비밀번호.
        new_password: 변경할 새 비밀번호 (영문+숫자 포함, 8~100자).
    """

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """새 비밀번호 복잡도를 검증한다.

        Args:
            v: 검증할 새 비밀번호 문자열.

        Returns:
            검증된 새 비밀번호 문자열.

        Raises:
            ValueError: 길이가 8~100자 범위를 벗어나거나 영문자·숫자가 포함되지 않은 경우.
        """
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다")
        if len(v) > 100:
            raise ValueError("비밀번호는 100자 이하여야 합니다")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("비밀번호에 영문자가 포함되어야 합니다")
        if not re.search(r"\d", v):
            raise ValueError("비밀번호에 숫자가 포함되어야 합니다")
        return v


class TokenResponse(BaseModel):
    """JWT 토큰 발급 응답 스키마.

    로그인 성공 시 클라이언트에 반환되는 액세스 토큰 정보.

    Attributes:
        access_token: JWT 액세스 토큰 문자열.
        token_type: 토큰 타입 (항상 'bearer').
    """

    access_token: str
    token_type: str = "bearer"


# ── Admin 전용 스키마 ──


class AdminUserDetailResponse(BaseModel):
    """관리자용 사용자 상세 (관계 카운트 + 크레딧 포함).

    관리자 대시보드에서 특정 사용자의 상세 정보를 조회할 때 사용한다.
    일반 UserResponse보다 더 많은 통계 필드를 포함한다.

    Attributes:
        id: 사용자 UUID.
        login_id: 로그인 아이디.
        nickname: 표시 닉네임.
        role: 역할.
        age_group: 연령 그룹.
        adult_verified_at: 성인 인증 일시 (선택).
        preferred_llm_model_id: 선호 LLM 모델 UUID (선택).
        preferred_themes: 선호 테마 목록 (선택).
        credit_balance: 현재 크레딧 잔액.
        last_credit_grant_at: 마지막 크레딧 지급 일시 (선택).
        created_at: 계정 생성 일시.
        updated_at: 마지막 수정 일시 (선택).
        session_count: 참여 세션 수.
        message_count: 발송 메시지 수.
        subscription_status: 구독 상태 (선택).
    """

    id: UUID
    login_id: str
    nickname: str
    role: str
    age_group: str
    adult_verified_at: datetime | None = None
    preferred_llm_model_id: UUID | None = None
    preferred_themes: list[str] | None = None
    credit_balance: int = 0
    last_credit_grant_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    session_count: int = 0
    message_count: int = 0
    subscription_status: str | None = None

    model_config = {"from_attributes": True}


class UserStats(BaseModel):
    """사용자 통계 집계 스키마.

    플랫폼 전체 사용자 현황을 역할·인증 상태별로 집계한 통계.

    Attributes:
        total_users: 전체 사용자 수.
        superadmin_count: 슈퍼관리자 수.
        admin_count: 관리자 수.
        adult_verified_count: 성인 인증 완료 사용자 수.
        unverified_count: 미인증 사용자 수.
        minor_safe_count: 미성년 안전 모드 사용자 수.
    """

    total_users: int = 0
    superadmin_count: int = 0
    admin_count: int = 0
    adult_verified_count: int = 0
    unverified_count: int = 0
    minor_safe_count: int = 0


class BulkDeleteRequest(BaseModel):
    """사용자 일괄 삭제 요청 스키마.

    최대 50명의 사용자를 한 번에 삭제 요청할 때 사용한다.

    Attributes:
        user_ids: 삭제할 사용자 UUID 목록 (최대 50개).
    """

    user_ids: list[UUID]

    @field_validator("user_ids")
    @classmethod
    def validate_max_ids(cls, v: list[UUID]) -> list[UUID]:
        """삭제 대상 ID 수를 검증한다.

        Args:
            v: 삭제할 사용자 UUID 목록.

        Returns:
            검증된 사용자 UUID 목록.

        Raises:
            ValueError: 목록에 50개를 초과하는 ID가 있는 경우.
        """
        if len(v) > 50:
            raise ValueError("최대 50명까지 선택 가능합니다")
        return v


class BulkDeleteResponse(BaseModel):
    """사용자 일괄 삭제 결과 응답 스키마.

    Attributes:
        deleted_count: 실제로 삭제된 사용자 수.
        skipped_admin_ids: 관리자 권한으로 인해 삭제가 건너뛰어진 사용자 UUID 목록.
    """

    deleted_count: int = 0
    skipped_admin_ids: list[UUID] = []
