"""JWT 인증 및 비밀번호 해싱 유틸리티.

bcrypt 기반 비밀번호 해싱, JWT 액세스 토큰 발급/검증,
Redis 기반 토큰 블랙리스트와 단일 세션 관리를 제공한다.
"""

import logging
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings  # JWT 설정 및 토큰 만료 시간 로드

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def verify_password(plain_password: str | None, hashed_password: str | None) -> bool:
    """평문 비밀번호와 bcrypt 해시를 비교 검증한다.

    입력값이 None이거나 빈 문자열이면 즉시 False를 반환한다.

    Args:
        plain_password: 사용자가 입력한 평문 비밀번호.
        hashed_password: DB에 저장된 bcrypt 해시 비밀번호.

    Returns:
        비밀번호 일치 여부.
    """
    if not plain_password or not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """평문 비밀번호를 bcrypt 해시로 변환한다.

    Args:
        password: 해싱할 평문 비밀번호.

    Returns:
        bcrypt 해시 문자열.
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """JWT 액세스 토큰을 생성한다.

    data에 exp 클레임을 추가하여 서명한다. sub 클레임에 사용자 ID를 포함시키는 것이
    관례이며, jti 클레임을 포함하면 단일 세션 관리에 활용된다.

    Args:
        data: 토큰 페이로드 데이터 (sub, jti 등 클레임 포함).
        expires_delta: 커스텀 만료 시간. None이면 설정값(access_token_expire_minutes) 사용.

    Returns:
        서명된 JWT 토큰 문자열.
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """JWT 토큰을 디코딩하여 페이로드를 반환한다.

    서명 검증 실패, 만료, 형식 오류 등 모든 JWTError는 None으로 처리한다.

    Args:
        token: 검증할 JWT 토큰 문자열.

    Returns:
        유효한 토큰이면 페이로드 딕셔너리, 유효하지 않으면 None.
    """
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


# --- 토큰 블랙리스트 (Redis 기반) ---
_BLACKLIST_PREFIX = "token_blacklist:"


async def blacklist_token(token: str) -> None:
    """토큰을 Redis 블랙리스트에 추가한다.

    토큰 만료 시간(exp)까지만 Redis에 유지하여 메모리를 절약한다.
    이미 만료된 토큰이거나 Redis 장애 시 조용히 무시한다.

    Args:
        token: 블랙리스트에 추가할 JWT 토큰 문자열.
    """
    from app.core.redis import redis_client  # 순환 임포트 방지를 위해 지연 임포트

    payload = decode_access_token(token)
    if payload is None:
        return
    exp = payload.get("exp", 0)
    ttl = max(int(exp - datetime.now(UTC).timestamp()), 0)
    if ttl > 0:
        try:
            await redis_client.setex(f"{_BLACKLIST_PREFIX}{token}", ttl, "1")
        except Exception:
            logger.warning("Failed to blacklist token (Redis unavailable)")


async def is_token_blacklisted(token: str) -> bool:
    """토큰이 블랙리스트에 등록되어 있는지 확인한다.

    Redis 장애 시 False를 반환하여 서비스를 유지한다(fail-open).
    로그아웃된 토큰 재사용을 방지하기 위해 매 인증 시 호출된다.

    Args:
        token: 확인할 JWT 토큰 문자열.

    Returns:
        블랙리스트에 등록된 토큰이면 True, 아니면 False.
    """
    from app.core.redis import redis_client  # 순환 임포트 방지를 위해 지연 임포트

    try:
        return await redis_client.exists(f"{_BLACKLIST_PREFIX}{token}") > 0
    except Exception:
        logger.warning("Failed to check token blacklist (Redis unavailable)")
        return False


# --- 단일 세션 관리 (Redis 기반) ---

_SESSION_PREFIX = "user_session:"


async def set_user_session(user_id: str, jti: str, ttl_seconds: int) -> None:
    """사용자 현재 세션 JTI를 Redis에 저장한다.

    동일 사용자가 재로그인하면 기존 JTI가 덮어쓰여 이전 세션이 자동 무효화된다.
    이를 통해 단일 세션(one-device) 정책을 강제한다.

    Args:
        user_id: 세션을 저장할 사용자 ID.
        jti: JWT ID 클레임 값 (토큰 고유 식별자).
        ttl_seconds: Redis 키 만료 시간 (초). 토큰 만료 시간과 일치시켜야 한다.
    """
    from app.core.redis import redis_client  # 순환 임포트 방지를 위해 지연 임포트

    try:
        await redis_client.setex(f"{_SESSION_PREFIX}{user_id}", ttl_seconds, jti)
    except Exception:
        logger.warning("Failed to set user session (Redis unavailable)")


async def get_user_session_jti(user_id: str) -> str | None:
    """저장된 사용자의 현재 세션 JTI를 조회한다.

    Redis 장애 시 None을 반환하여 인증을 통과시킨다(fail-open).
    None 반환은 세션 무효화가 아닌 Redis 장애로 해석해야 한다.

    Args:
        user_id: 조회할 사용자 ID.

    Returns:
        저장된 JTI 문자열, 세션이 없거나 Redis 장애면 None.
    """
    from app.core.redis import redis_client  # 순환 임포트 방지를 위해 지연 임포트

    try:
        val = await redis_client.get(f"{_SESSION_PREFIX}{user_id}")
        if val is None:
            return None
        return val.decode() if isinstance(val, bytes) else val
    except Exception:
        logger.warning("Failed to get user session JTI (Redis unavailable)")
        return None


async def clear_user_session(user_id: str) -> None:
    """로그아웃 시 사용자 세션 JTI를 Redis에서 삭제한다.

    이후 해당 사용자의 모든 기존 토큰은 단일 세션 검증에서 거부된다.
    Redis 장애 시 조용히 무시한다.

    Args:
        user_id: 세션을 삭제할 사용자 ID.
    """
    from app.core.redis import redis_client  # 순환 임포트 방지를 위해 지연 임포트

    try:
        await redis_client.delete(f"{_SESSION_PREFIX}{user_id}")
    except Exception:
        logger.warning("Failed to clear user session (Redis unavailable)")
