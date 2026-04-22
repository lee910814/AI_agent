"""로컬 에이전트 WebSocket 엔드포인트."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token, get_user_session_jti, is_token_blacklisted
from app.core.config import settings
from app.core.database import async_session
from app.models.debate_agent import DebateAgent
from app.models.user import User
from app.services.debate.ws_manager import WSConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter()

_AUTH_TIMEOUT = 10.0


async def _authenticate_ws(token: str, db: AsyncSession) -> tuple[User, None] | tuple[None, str]:
    """JWT 토큰으로 WebSocket 사용자 인증.

    블랙리스트 체크와 세션 JTI 검증을 추가로 수행한다.
    Redis 장애 시에는 인증을 통과시켜 WS 완전 차단을 방지한다.
    """
    payload = decode_access_token(token)
    if payload is None:
        return None, "Invalid or expired token"

    user_id = payload.get("sub")
    if not user_id:
        return None, "Invalid token payload"

    # 토큰 블랙리스트 확인 (Redis 장애 시 fail-open)
    if await is_token_blacklisted(token):
        return None, "Token has been revoked"

    # JTI 기반 단일 세션 검증 — jti 클레임이 없는 구형 토큰은 스킵
    jti = payload.get("jti")
    if jti is not None:
        active_jti = await get_user_session_jti(user_id)
        # active_jti가 None이면 Redis 장애로 간주하고 통과
        if active_jti is not None and active_jti != jti:
            return None, "Session has been superseded by a newer login"

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None, "User not found"

    return user, None


@router.websocket("/ws/agent/{agent_id}")
async def agent_websocket(
    websocket: WebSocket,
    agent_id: UUID,
) -> None:
    """로컬 에이전트 WebSocket 엔드포인트.

    토큰을 URL 쿼리 파라미터 대신 연결 후 첫 메시지로 수신한다.
    클라이언트는 연결 즉시 {"type": "auth", "token": "<JWT>"} 를 전송해야 한다.
    """
    await websocket.accept()

    # 1. 첫 메시지로 인증 정보 수신 (10초 타임아웃)
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=_AUTH_TIMEOUT)
    except TimeoutError:
        await websocket.close(code=4001, reason="Auth timeout")
        return
    except Exception as exc:
        logger.warning("Agent %s auth message receive error: %s", agent_id, exc)
        await websocket.close(code=4001, reason="Auth message error")
        return

    if not isinstance(auth_msg, dict) or auth_msg.get("type") != "auth" or not auth_msg.get("token"):
        await websocket.close(code=4001, reason="Invalid auth message format")
        return

    token: str = auth_msg["token"]

    async with async_session() as db:
        # 2. JWT 검증 (블랙리스트 + JTI 포함)
        user, error = await _authenticate_ws(token, db)
        if user is None:
            await websocket.close(code=4001, reason=error)
            return

        # 3. 에이전트 소유권 + provider 검증
        result = await db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id)
        )
        agent = result.scalar_one_or_none()

        if agent is None:
            await websocket.close(code=4004, reason="Agent not found")
            return
        if agent.owner_id != user.id:
            await websocket.close(code=4003, reason="Not owner of this agent")
            return
        if agent.provider != "local":
            await websocket.close(code=4003, reason="Agent is not a local provider")
            return

    # 4. 연결 등록
    manager = WSConnectionManager.get_instance()
    await manager.connect(agent_id, websocket)

    # 5. heartbeat 태스크
    async def heartbeat_loop() -> None:
        while True:
            await asyncio.sleep(settings.debate_ws_heartbeat_interval)
            try:
                await manager.send_ping(agent_id)
            except Exception:
                break

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        # 6. 메시지 수신 루프
        while True:
            data = await websocket.receive_json()
            await manager.handle_message(agent_id, data)
    except WebSocketDisconnect:
        logger.info("Agent %s WebSocket disconnected normally", agent_id)
    except Exception as exc:
        logger.warning("Agent %s WebSocket error: %s", agent_id, exc)
    finally:
        heartbeat_task.cancel()
        await manager.disconnect(agent_id)
