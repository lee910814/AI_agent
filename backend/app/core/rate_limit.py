"""Redis 기반 슬라이딩 윈도우 Rate Limiter.

Sorted Set을 사용한 슬라이딩 윈도우 알고리즘으로 요청 빈도를 제한한다.
키 패턴: rate_limit:{identifier}:{route_group}
"""

import logging
import time
import uuid

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings  # rate limit 임계값 및 윈도우 설정 로드
from app.core.redis import redis_client  # Sorted Set 기반 슬라이딩 윈도우 카운터용

logger = logging.getLogger(__name__)

# Rate limit을 적용하지 않는 경로
BYPASS_PATHS = {"/health", "/metrics"}

# route group → (limit, window) 매핑을 설정에서 동적 구성
ROUTE_GROUP_PREFIXES = [
    ("/api/admin", "admin"),
    ("/api/auth", "auth"),
    # 토론 라우트: SSE 스트림 연결 + 다수 폴링 요청으로 일반 limit 초과 빈발
    ("/api/matches", "debate"),
    ("/api/topics", "debate"),
    ("/api/agents", "debate"),
    ("/api/tournaments", "debate"),
]


def _get_route_group(path: str) -> str:
    """요청 경로에서 rate limit 그룹을 결정한다.

    ROUTE_GROUP_PREFIXES를 순서대로 검사하여 첫 번째 일치하는 그룹을 반환한다.
    일치하는 항목이 없으면 기본 그룹 "api"를 반환한다.

    Args:
        path: 요청 URL 경로 (예: "/api/matches/123/stream").

    Returns:
        rate limit 그룹 이름 (admin, auth, debate, api 중 하나).
    """
    for prefix, group in ROUTE_GROUP_PREFIXES:
        if path.startswith(prefix):
            return group
    return "api"


def _get_rate_limit_config(route_group: str) -> tuple[int, int]:
    """route group에 대한 rate limit 설정을 반환한다.

    Args:
        route_group: 조회할 route 그룹 이름 (admin, auth, debate, api).

    Returns:
        (limit, window_seconds) 튜플.
        limit: 윈도우 내 허용 최대 요청 수.
        window_seconds: 슬라이딩 윈도우 크기 (초).
    """
    limit_map = {
        "auth": settings.rate_limit_auth,
        "api": settings.rate_limit_api,
        "debate": settings.rate_limit_debate,
        "admin": settings.rate_limit_admin,
    }
    limit = limit_map.get(route_group, settings.rate_limit_api)
    return limit, settings.rate_limit_window


def _extract_identifier(request: Request) -> str:
    """요청에서 rate limit 식별자를 추출한다.

    Authorization 헤더의 JWT에서 sub 클레임(사용자 ID)을 우선 추출한다.
    인증되지 않은 요청은 X-Real-IP → X-Forwarded-For → 소켓 IP 순으로 fallback한다.

    Args:
        request: 현재 Starlette 요청 객체.

    Returns:
        rate limit 키에 사용할 식별자 문자열.
        인증된 사용자는 "user:{user_id}", 미인증은 "ip:{ip_address}" 형태.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except JWTError:
            pass

    # 인증 실패 또는 토큰 없음 → X-Real-IP (nginx 프록시 헤더) 우선, 없으면 소켓 IP
    real_ip = (
        request.headers.get("x-real-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    return f"ip:{real_ip}"


async def check_rate_limit(identifier: str, route_group: str) -> tuple[bool, int, int, int]:
    """슬라이딩 윈도우 알고리즘으로 rate limit을 검사한다.

    Redis Sorted Set에 타임스탬프를 저장하고 윈도우 밖의 항목을 제거하여
    정확한 슬라이딩 윈도우 카운팅을 구현한다. Pipeline으로 원자적 실행한다.

    Args:
        identifier: rate limit 식별자 ("user:{id}" 또는 "ip:{ip}").
        route_group: route 그룹 이름 (limit 설정 조회에 사용).

    Returns:
        (allowed, limit, remaining, reset_timestamp) 튜플.
        allowed: 요청 허용 여부.
        limit: 윈도우 내 최대 허용 요청 수.
        remaining: 남은 허용 요청 수.
        reset_timestamp: 윈도우 초기화 예상 Unix 타임스탬프.
    """
    limit, window = _get_rate_limit_config(route_group)
    now = time.time()
    window_start = now - window
    reset_at = int(now) + window
    key = f"rate_limit:{identifier}:{route_group}"

    pipe = redis_client.pipeline()
    # 윈도우 밖의 오래된 항목 제거
    pipe.zremrangebyscore(key, 0, window_start)
    # 동일 타임스탬프 충돌 방지 — member를 유니크하게
    member = f"{now}:{uuid.uuid4().hex[:8]}"
    pipe.zadd(key, {member: now})
    # 현재 윈도우 내 요청 수
    pipe.zcard(key)
    # 키 TTL 설정 (윈도우 크기 + 여유 1초)
    pipe.expire(key, window + 1)
    results = await pipe.execute()

    current_count = results[2]
    remaining = max(0, limit - current_count)
    allowed = current_count <= limit

    return allowed, limit, remaining, reset_at


class RateLimitMiddleware(BaseHTTPMiddleware):
    """슬라이딩 윈도우 rate limit을 모든 요청에 적용하는 Starlette 미들웨어.

    요청 경로에 따라 route 그룹을 분류하고, 인증된 사용자 ID 또는 IP를
    식별자로 사용하여 Redis에 카운터를 관리한다.
    Redis 장애 시 graceful degradation으로 요청을 허용한다.

    설정:
        BYPASS_PATHS: rate limit을 적용하지 않는 경로 목록.
        ROUTE_GROUP_PREFIXES: 경로 접두사별 rate limit 그룹 매핑.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """요청에 rate limit을 적용하고 응답 헤더에 rate limit 정보를 추가한다.

        SSE 스트림(/stream으로 끝나는 경로)은 별도 debate 한도의 절반으로 제한한다.
        허용된 요청은 X-RateLimit-* 헤더를 응답에 추가한다.

        Args:
            request: 처리할 Starlette 요청 객체.
            call_next: 다음 미들웨어 또는 라우터 핸들러.

        Returns:
            rate limit 통과 시 실제 응답 (X-RateLimit-* 헤더 포함),
            초과 시 429 JSONResponse.
        """
        # rate limit 비활성화 시 바이패스
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # 헬스체크, 메트릭 등 바이패스 경로
        if request.url.path in BYPASS_PATHS:
            return await call_next(request)

        # SSE 스트림은 지속 연결이라 요청당 카운팅 부적합.
        # 단, 연결 시도 자체는 debate limit의 절반으로 제한해 무제한 연결 방지.
        if request.url.path.endswith("/stream"):
            identifier = _extract_identifier(request)
            stream_limit = max(settings.rate_limit_debate // 2, 10)
            _, window = _get_rate_limit_config("debate")
            now = time.time()
            window_start = now - window
            reset_at = int(now) + window
            key = f"rate_limit:{identifier}:stream"
            try:
                pipe = redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                member = f"{now}:{uuid.uuid4().hex[:8]}"
                pipe.zadd(key, {member: now})
                pipe.zcard(key)
                pipe.expire(key, window + 1)
                results = await pipe.execute()
                current_count = results[2]
                if current_count > stream_limit:
                    retry_after = reset_at - int(now)
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "Too many stream connections",
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "retry_after": retry_after,
                        },
                        headers={
                            "X-RateLimit-Limit": str(stream_limit),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(reset_at),
                            "Retry-After": str(retry_after),
                        },
                    )
            except Exception:
                # Redis 장애 시 연결 허용 (graceful degradation)
                logger.warning("Stream rate limit check failed (Redis unavailable), allowing request", exc_info=True)
            return await call_next(request)

        identifier = _extract_identifier(request)
        route_group = _get_route_group(request.url.path)

        try:
            allowed, limit, remaining, reset_at = await check_rate_limit(identifier, route_group)
        except Exception:
            # Redis 장애 시 요청을 허용한다 (graceful degradation)
            logger.warning("Rate limit check failed (Redis unavailable), allowing request", exc_info=True)
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": reset_at - int(time.time()),
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(reset_at - int(time.time())),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response
