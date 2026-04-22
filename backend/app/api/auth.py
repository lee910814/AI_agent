"""인증 API 라우터 — 회원가입, 로그인, 로그아웃, 프로필 수정."""

import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    blacklist_token,
    clear_user_session,
    create_access_token,
    decode_access_token,
    set_user_session,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import PasswordChange, TokenResponse, UserCreate, UserLogin, UserResponse, UserUpdate
from app.services.user_service import UserService

# auto_error=False: 쿠키 기반 인증 fallback 허용
_bearer = HTTPBearer(auto_error=False)


def _set_auth_cookie(response: Response, token: str) -> None:
    """HttpOnly 쿠키로 JWT 설정.

    Args:
        response: FastAPI Response 객체.
        token: 설정할 JWT 액세스 토큰 문자열.
    """
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        # HTTPS 환경에서만 secure=True (개발 환경 편의상 dev에서는 False)
        secure=settings.app_env != "development",
    )


def _clear_auth_cookie(response: Response) -> None:
    """인증 쿠키 삭제.

    Args:
        response: FastAPI Response 객체.
    """
    response.delete_cookie(key="access_token", samesite="lax")

router = APIRouter()


@router.get("/check-nickname")
async def check_nickname(nickname: str, db: AsyncSession = Depends(get_db)):
    """닉네임 사용 가능 여부 확인.

    Args:
        nickname: 중복 체크할 닉네임.
        db: 비동기 DB 세션.

    Returns:
        available 필드가 포함된 딕셔너리.
    """
    service = UserService(db)
    available = await service.check_nickname_available(nickname)
    return {"available": available}


@router.get("/check-login-id")
async def check_login_id(login_id: str, db: AsyncSession = Depends(get_db)):
    """아이디 사용 가능 여부 확인.

    Args:
        login_id: 중복 체크할 로그인 ID.
        db: 비동기 DB 세션.

    Returns:
        available 필드가 포함된 딕셔너리.
    """
    service = UserService(db)
    available = await service.check_login_id_available(login_id)
    return {"available": available}


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate, response: Response, db: AsyncSession = Depends(get_db)):
    """사용자 회원가입 → JWT 발급 + HttpOnly 쿠키 설정.

    Args:
        data: 회원가입 요청 데이터 (login_id, nickname, password).
        response: 쿠키 설정을 위한 FastAPI Response 객체.
        db: 비동기 DB 세션.

    Returns:
        TokenResponse — 발급된 JWT 액세스 토큰.

    Raises:
        HTTPException(400): login_id 또는 nickname에 'admin' 포함 시.
        HTTPException(409): 닉네임 중복 시.
    """
    # 관리자 사칭 방지 — 일반 가입에서 'admin' 포함 login_id/닉네임 차단
    if "admin" in data.login_id.lower() or "admin" in data.nickname.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID and nickname cannot contain 'admin'",
        )
    service = UserService(db)
    try:
        user = await service.create_user(data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nickname already taken",
        ) from None
    jti = str(uuid.uuid4())
    token = create_access_token({"sub": str(user.id), "role": user.role, "jti": jti})
    await set_user_session(str(user.id), jti, settings.access_token_expire_minutes * 60)
    _set_auth_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    """로그인 → JWT 발급 + HttpOnly 쿠키 설정. 이전 세션은 자동 무효화(단일 세션).

    Args:
        data: 로그인 요청 데이터 (login_id, password).
        response: 쿠키 설정을 위한 FastAPI Response 객체.
        db: 비동기 DB 세션.

    Returns:
        TokenResponse — 발급된 JWT 액세스 토큰.

    Raises:
        HTTPException(401): 인증 실패 (아이디/비밀번호 불일치) 시.
    """
    service = UserService(db)
    user = await service.authenticate(data)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    jti = str(uuid.uuid4())
    token = create_access_token({"sub": str(user.id), "role": user.role, "jti": jti})
    # 새 JTI로 덮어쓰면 이전 기기 세션은 다음 요청 시 AUTH_SESSION_REPLACED로 차단됨
    await set_user_session(str(user.id), jti, settings.access_token_expire_minutes * 60)
    _set_auth_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/logout")
async def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Cookie(default=None),
):
    """로그아웃. 현재 토큰을 블랙리스트에 추가하고 세션을 삭제한다.

    Args:
        response: 쿠키 삭제를 위한 FastAPI Response 객체.
        credentials: Authorization 헤더 Bearer 토큰 (선택).
        access_token: HttpOnly 쿠키 토큰 (선택).

    Returns:
        성공 메시지 딕셔너리.
    """
    token = credentials.credentials if credentials else access_token
    if token:
        await blacklist_token(token)
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            await clear_user_session(payload["sub"])
    _clear_auth_cookie(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """현재 로그인 사용자 정보.

    Args:
        user: 인증된 현재 사용자.

    Returns:
        UserResponse — 현재 사용자 프로필 정보.
    """
    return user


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로필 정보 수정 (닉네임).

    Args:
        data: 수정할 프로필 데이터 (nickname).
        user: 인증된 현재 사용자.
        db: 비동기 DB 세션.

    Returns:
        UserResponse — 수정된 사용자 프로필 정보.

    Raises:
        HTTPException(400): 일반 사용자가 'admin' 포함 닉네임으로 변경 시도 시.
        HTTPException(409): 닉네임 중복 시.
    """
    # 일반 유저가 'admin' 포함 닉네임으로 변경하는 것 차단
    if data.nickname and "admin" in data.nickname.lower() and user.role == "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nickname cannot contain 'admin'",
        )
    service = UserService(db)
    try:
        updated = await service.update_profile(user, data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nickname already taken",
        ) from None
    return updated


@router.put("/me/password")
async def change_password(
    data: PasswordChange,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Cookie(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비밀번호 변경. 성공 시 현재 토큰 무효화 + 새 토큰 발급 + 쿠키 갱신.

    Args:
        data: 현재 비밀번호와 새 비밀번호.
        response: 쿠키 갱신을 위한 FastAPI Response 객체.
        credentials: Authorization 헤더 Bearer 토큰 (선택).
        access_token: HttpOnly 쿠키 토큰 (선택).
        user: 인증된 현재 사용자.
        db: 비동기 DB 세션.

    Returns:
        성공 메시지와 새로 발급된 액세스 토큰.

    Raises:
        HTTPException(400): 현재 비밀번호가 틀렸을 때.
    """
    service = UserService(db)
    success = await service.change_password(user, data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    # 현재 토큰 무효화
    old_token = credentials.credentials if credentials else access_token
    if old_token:
        await blacklist_token(old_token)
    # 새 토큰 발급 + 쿠키 갱신 (새 JTI로 세션 갱신)
    jti = str(uuid.uuid4())
    new_token = create_access_token({"sub": str(user.id), "role": user.role, "jti": jti})
    await set_user_session(str(user.id), jti, settings.access_token_expire_minutes * 60)
    _set_auth_cookie(response, new_token)
    return {"message": "Password changed successfully", "access_token": new_token}
