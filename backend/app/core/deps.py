"""FastAPI Depends 의존성 주입 함수 모음.

인증·권한 검사를 위한 의존성 함수를 제공한다.
라우터에서 Depends(get_current_user), Depends(require_admin) 등으로 사용한다.
"""

from datetime import UTC, datetime

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token, get_user_session_jti, is_token_blacklisted  # JWT 유틸리티
from app.core.database import get_db  # DB 세션 의존성
from app.models.user import User  # 사용자 ORM 모델

# auto_error=False: Authorization 헤더가 없어도 에러 미발생 (쿠키로 fallback)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT에서 현재 인증된 사용자를 추출한다.

    Authorization 헤더(Bearer 토큰)와 access_token 쿠키를 모두 지원하며,
    헤더가 쿠키보다 우선한다. 블랙리스트 토큰, 단일 세션 위반, 밴 계정은 거부한다.

    Args:
        credentials: Authorization 헤더의 Bearer 토큰. 없으면 None.
        access_token: access_token 쿠키 값. 없으면 None.
        db: 비동기 DB 세션.

    Returns:
        인증된 User ORM 인스턴스.

    Raises:
        HTTPException: 토큰 없음(401), 유효하지 않은 토큰(401),
            토큰 블랙리스트(401), 세션 만료(401), 사용자 없음(401),
            계정 밴(403) 등 인증 실패 시.
    """
    token = credentials.credentials if credentials else access_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # 토큰 블랙리스트 확인 (로그아웃된 토큰 차단)
    if await is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # 단일 세션 강제: jti가 있으면 Redis에 저장된 현재 세션 JTI와 비교
    jti = payload.get("jti")
    if jti:
        current_jti = await get_user_session_jti(user_id)
        # current_jti가 None이면 Redis 장애 → fail-open (서비스 중단 방지)
        if current_jti is not None and current_jti != jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired: logged in from another device",
                headers={"X-Error-Code": "AUTH_SESSION_REPLACED"},
            )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # 밴 상태 확인
    if user.banned_until is not None and user.banned_until > datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account banned until {user.banned_until.isoformat()}",
            headers={"X-Error-Code": "USER_BANNED"},
        )

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """관리자 역할(admin 또는 superadmin)인 경우에만 통과시킨다.

    일반 사용자가 관리자 API에 접근하면 403을 반환한다.

    Args:
        user: get_current_user로 인증된 사용자.

    Returns:
        admin 또는 superadmin 역할의 User 인스턴스.

    Raises:
        HTTPException: 역할이 admin/superadmin이 아닌 경우 403.
    """
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def require_superadmin(user: User = Depends(get_current_user)) -> User:
    """슈퍼관리자 역할(superadmin)인 경우에만 통과시킨다.

    사용자 삭제, 역할 변경, 시스템 설정 등 파괴적 작업에 사용한다.

    Args:
        user: get_current_user로 인증된 사용자.

    Returns:
        superadmin 역할의 User 인스턴스.

    Raises:
        HTTPException: 역할이 superadmin이 아닌 경우 403.
    """
    if user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return user

