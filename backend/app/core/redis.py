"""Redis 클라이언트 싱글턴 및 Pub/Sub 전용 클라이언트 설정.

일반 커맨드용 클라이언트(redis_client)와 SSE Pub/Sub 전용 클라이언트(pubsub_client)를
분리 관리한다. Subscribe 상태에서는 일반 커맨드를 실행할 수 없으므로 클라이언트를 분리한다.
"""

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from app.core.config import settings  # Redis URL 로드

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

# pub/sub 전용 클라이언트 — subscribe 상태에서는 다른 명령 불가이므로 일반 클라이언트와 분리.
# ConnectionPool을 명시적으로 생성해 동시 SSE 연결 수를 max_connections으로 상한 제어.
_pubsub_pool = ConnectionPool.from_url(
    settings.redis_url,
    decode_responses=True,
    max_connections=200,
)
pubsub_client = Redis(connection_pool=_pubsub_pool)


async def get_redis() -> Redis:
    """FastAPI Depends에서 사용할 Redis 클라이언트 반환.

    일반 Redis 커맨드(GET, SET, EXPIRE 등)에 사용한다.
    Pub/Sub 구독에는 pubsub_client를 직접 사용해야 한다.

    Returns:
        Redis: 공유 비동기 Redis 클라이언트 인스턴스.
    """
    return redis_client
