"""Redis pub/sub 기반 SSE 브로드캐스트 — 매치 관전 + 매칭 큐 이벤트 통합 모듈."""

import json
import logging
import time
from collections.abc import AsyncGenerator

from redis.asyncio.client import PubSub

from app.core.redis import pubsub_client, redis_client  # 공유 연결 풀

logger = logging.getLogger(__name__)


# ── SSE 이벤트 브로드캐스트 (매치 관전자용) ────────────────────────────────────


def _channel(match_id: str) -> str:
    """매치 이벤트 Redis 채널명 반환."""
    return f"debate:match:{match_id}"


async def publish_event(match_id: str, event_type: str, data: dict) -> None:
    """토론 이벤트를 Redis 채널에 발행. 공유 클라이언트 사용 — 청크 단위 호출 시 연결 생성 오버헤드 제거."""
    payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False, default=str)
    await redis_client.publish(_channel(match_id), payload)


async def subscribe(match_id: str, user_id: str, max_wait_seconds: int = 600) -> AsyncGenerator[str, None]:
    """Redis pub/sub 구독. SSE 형식 문자열을 yield.

    max_wait_seconds 내에 finished/error 이벤트가 오지 않으면 timeout 에러를 발행하고 종료.
    엔진 크래시/서버 재시작으로 이벤트가 누락된 경우 클라이언트가 fetchMatch를 호출해 상태를 갱신하도록 유도.
    """
    pubsub = pubsub_client.pubsub()
    await pubsub.subscribe(_channel(match_id))

    # 관전자 수 추적 — user_id를 Set 멤버로 사용해 새로고침 시 중복 카운트 방지
    viewers_key = f"debate:viewers:{match_id}"
    try:
        await redis_client.sadd(viewers_key, user_id)
        await redis_client.expire(viewers_key, 3600)
    except Exception:
        logger.warning("Failed to add viewer for match %s", match_id)

    deadline = time.monotonic() + max_wait_seconds

    try:
        async for sse_line in _poll_pubsub(pubsub, _MATCH_TERMINAL_EVENTS, deadline):
            yield sse_line

        if time.monotonic() >= deadline:
            # 엔진 크래시 또는 비정상 종료로 이벤트 미수신
            timeout_payload = json.dumps(
                {"event": "error", "data": {"message": "Stream timeout: match may have failed"}},
                ensure_ascii=False,
            )
            yield f"data: {timeout_payload}\n\n"
            logger.warning("SSE subscribe timeout for match %s after %ds", match_id, max_wait_seconds)
    finally:
        await pubsub.unsubscribe(_channel(match_id))
        await pubsub.aclose()
        try:
            await redis_client.srem(viewers_key, user_id)
        except Exception:
            logger.warning("Failed to remove viewer for match %s", match_id)


# ── 매칭 큐 상태 브로드캐스트 (Redis Pub/Sub) ────────────────────────────────────
# 채널: debate:queue:{topic_id}:{agent_id}
# 이벤트: matched, timeout, cancelled, opponent_joined, countdown_started
# matched / timeout / cancelled 수신 시 스트림 종료.

_TERMINAL_EVENTS = {"matched", "timeout", "cancelled"}

_MATCH_TERMINAL_EVENTS = {"finished", "error", "forfeit"}


async def _poll_pubsub(
    pubsub: PubSub,
    terminal_events: set[str],
    deadline: float,
) -> AsyncGenerator[str, None]:
    """Redis pub/sub 메시지를 SSE 형식으로 yield하는 공통 폴링 루프.

    deadline 초과 시 루프를 종료하고 제어를 호출자에게 반환.
    타임아웃 이벤트 발행은 호출자(subscribe/subscribe_queue)가 담당한다.

    Args:
        pubsub: Redis PubSub 인스턴스 (이미 채널 구독 완료).
        terminal_events: 수신 시 루프를 종료할 이벤트 타입 집합.
        deadline: monotonic 기준 종료 시각.

    Yields:
        'data: {...}\\n\\n' 또는 ': heartbeat\\n\\n' 형식의 SSE 문자열.
    """
    while time.monotonic() < deadline:
        # 즉시 폴링 후 없으면 블로킹 대기 — 중복 메시지 처리 로직 통합
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.05)
        if message is None:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2.0)

        if message is not None and message["type"] == "message":
            data = message["data"]
            yield f"data: {data}\n\n"
            try:
                if json.loads(data).get("event") in terminal_events:
                    return
            except (json.JSONDecodeError, AttributeError):
                logger.warning("Malformed SSE payload: %.200s", data)
        else:
            yield ": heartbeat\n\n"


def _queue_channel(topic_id: str, agent_id: str) -> str:
    """큐 이벤트 Redis 채널명 반환."""
    return f"debate:queue:{topic_id}:{agent_id}"


async def publish_queue_event(topic_id: str, agent_id: str, event_type: str, data: dict) -> None:
    """큐 이벤트를 Redis 채널에 best-effort 발행.

    Redis 장애 시 예외를 내부에서 처리하고 로깅만 남긴다.
    DB commit 이후에 호출되므로 실패해도 큐 등록/매치 생성 상태는 유지된다.
    """
    if not topic_id or not agent_id:
        logger.warning("publish_queue_event: topic_id 또는 agent_id가 None — 발행 생략")
        return
    try:
        payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False, default=str)
        await redis_client.publish(_queue_channel(topic_id, agent_id), payload)
    except Exception:
        logger.error(
            "publish_queue_event 실패 (topic=%s agent=%s event=%s)",
            topic_id, agent_id, event_type, exc_info=True,
        )


async def subscribe_queue(
    topic_id: str,
    agent_id: str,
    max_wait_seconds: int = 120,
) -> AsyncGenerator[str, None]:
    """Redis pub/sub 구독. SSE 형식 문자열을 yield. 종료 이벤트 수신 또는 타임아웃 시 스트림 종료.

    max_wait_seconds: 큐 대기 최대 시간 (기본 120초). 초과 시 timeout 이벤트를 발행하고 종료.
    """
    pubsub = pubsub_client.pubsub()
    channel = _queue_channel(topic_id, agent_id)
    await pubsub.subscribe(channel)

    deadline = time.monotonic() + max_wait_seconds

    try:
        async for sse_line in _poll_pubsub(pubsub, _TERMINAL_EVENTS, deadline):
            yield sse_line

        if time.monotonic() >= deadline:
            timeout_payload = json.dumps(
                {"event": "timeout", "data": {"reason": "queue_timeout"}},
                default=str,
            )
            yield f"data: {timeout_payload}\n\n"
            logger.warning(
                "Queue subscribe timeout for topic=%s agent=%s after %ds",
                topic_id, agent_id, max_wait_seconds,
            )
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()